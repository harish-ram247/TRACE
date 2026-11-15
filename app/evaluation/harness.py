"""Run system variants over the evaluation questions and save every raw output.

Outputs go to eval/runs/<run_id>/:
  meta.json       what was run: variants, split, model, prompt version, git commit, dataset hash
  outputs.jsonl   one record per (question, variant): answer, citations, retrieved chunks, timing

Runs are resumable: records already in outputs.jsonl are skipped, so a run that stops on the
free-tier daily quota continues the next day with the same run id. Metrics are computed from
the saved outputs by app/evaluation/metrics.py, never during the run, so they can be recomputed
without calling the model again.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from app.core.llm import LLMClient, LLMError
from app.generation.answer import PROMPT_VERSION
from app.pipeline import Variant, ask
from app.retrieval.embeddings import Embedder
from app.verification.claims import EXTRACT_VERSION, extract_claims
from app.verification.nli import NLIModel
from app.verification.verify import DEFAULT_THRESHOLD, verify_claims

log = logging.getLogger(__name__)

RUNS_DIR = Path("eval/runs")


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    dataset: Path
    split: str  # "dev" | "test" | "all"
    variants: tuple[Variant, ...]
    repo_id: str
    top_k: int = 5
    limit: int | None = None
    threshold: float = DEFAULT_THRESHOLD
    # Extract and check claims of non-verified variants too (analysis only: the answer is not
    # changed), so claim-level metrics are comparable across all variants.
    analyze_claims: bool = True


def load_questions(path: Path, split: str = "all") -> list[dict]:
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    return [q for q in rows if split == "all" or q["split"] == split]


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _done_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            keys.add((rec["question_id"], rec["variant"]))
    return keys


def _final_claims(result, analysis: list | None) -> list[dict]:
    """Claims of the answer as finally returned, with their verdicts."""
    v = result.verification
    if v is None:
        return [vars(x) for x in analysis or []]
    if v.action == "keep":
        return [vars(x) for x in v.verdicts]
    if v.action == "revised":
        return [vars(x) for x in v.revised_verdicts]
    if v.action == "dropped_claims":
        pool = v.revised_verdicts or v.verdicts
        return [vars(x) for x in pool if x.label == "supported_current"]
    return []


def _record(q: dict, variant: str, result, analysis: list | None = None) -> dict:
    t = result.time
    return {
        "question_id": q["id"],
        "variant": variant,
        "answer": result.answer.text,
        "not_found": result.answer.not_found,
        "called_llm": result.answer.called_llm,
        "cited_chunk_ids": [c.chunk_id for c in result.answer.citations],
        "invalid_citations": result.answer.invalid_citations,
        "uncited": result.answer.uncited,
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "lineage_id": h.lineage_id,
                "source_path": h.source_path,
                "section_path": h.section_path,
                "valid_from": h.valid_from.isoformat(),
                "valid_until": h.valid_until.isoformat() if h.valid_until else None,
            }
            for h in result.hits
        ],
        "time": None
        if t is None
        else {
            "as_of": t.as_of.isoformat(),
            "intent": t.intent,
            "source": t.source,
            "matched": t.matched,
            "assumed": t.assumed,
            "notes": list(t.notes),
        },
        "model": result.answer.model,
        "prompt_version": result.answer.prompt_version,
        "cached": result.answer.cached,
        "tokens_in": result.answer.tokens_in,
        "tokens_out": result.answer.tokens_out,
        "timings_ms": result.timings_ms,
        "verification": result.verification.to_json() if result.verification else None,
        "final_claims": _final_claims(result, analysis),
    }


def run(
    conn: psycopg.Connection,
    config: RunConfig,
    *,
    embedder: Embedder,
    llm: LLMClient,
    nli: NLIModel | None = None,
    runs_dir: Path = RUNS_DIR,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Run every variant on every question of the split. Returns the run directory."""
    out_dir = runs_dir / config.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"
    if not meta_path.exists():
        meta = {
            "run_id": config.run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "dataset": str(config.dataset),
            "dataset_sha256": _sha256(config.dataset),
            "split": config.split,
            "variants": list(config.variants),
            "repo_id": config.repo_id,
            "top_k": config.top_k,
            "embedding_model": embedder.name,
            "llm_model": llm.name,
            "prompt_version": PROMPT_VERSION,
            "claims_version": EXTRACT_VERSION,
            "nli_model": nli.name if nli else None,
            "threshold": config.threshold,
            "analyze_claims": config.analyze_claims,
            "git_commit": _git_commit(),
        }
        meta_path.write_text(json.dumps(meta, indent=1), "utf-8")
    else:
        meta = json.loads(meta_path.read_text("utf-8"))
        if meta["dataset_sha256"] != _sha256(config.dataset):
            raise RuntimeError("dataset changed since this run started; use a new run id")

    questions = load_questions(config.dataset, config.split)
    if config.limit:
        questions = questions[: config.limit]
    outputs = out_dir / "outputs.jsonl"
    done = _done_keys(outputs)
    todo: Iterable[tuple[dict, str]] = [
        (q, v) for q in questions for v in config.variants if (q["id"], v) not in done
    ]
    todo = list(todo)
    say = progress or (lambda m: log.info(m))
    say(f"{len(done)} already done, {len(todo)} to run")

    with outputs.open("a", encoding="utf-8") as fh:
        for i, (q, variant) in enumerate(todo, start=1):
            try:
                result = ask(
                    conn,
                    q["question"],
                    embedder=embedder,
                    llm=llm,
                    repo_id=config.repo_id,
                    variant=variant,
                    now=datetime.fromisoformat(q["now"]),
                    top_k=config.top_k,
                    nli=nli,
                    threshold=config.threshold,
                )
                analysis = None
                if (
                    config.analyze_claims
                    and nli is not None
                    and result.verification is None
                    and not result.answer.not_found
                ):
                    claims = extract_claims(llm, result.answer.text).claims
                    analysis = verify_claims(claims, result.hits, nli, None, config.threshold)
            except LLMError as exc:
                say(f"stopping at {i - 1}/{len(todo)}: {exc} (re-run the same command to resume)")
                break
            fh.write(json.dumps(_record(q, variant, result, analysis)) + "\n")
            fh.flush()
            if i % 10 == 0 or i == len(todo):
                say(f"{i}/{len(todo)} done")
    return out_dir
