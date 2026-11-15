"""Run the evaluation and score it.

Usage:
  python -m scripts.run_eval --split dev --variants plain,temporal,plain_verified,temporal_verified
                             [--run-id ID] [--limit N] [--threshold 0.5]
  python -m scripts.run_eval --score-only --run-id ID

The run is resumable: if it stops (for example on the free tier's daily quota), run the same
command with the same --run-id to continue. Scoring reads only the saved files and writes
report.md, results.json, scored.jsonl, failures.csv and manual_checks_todo.csv into the run dir.

To apply hand checks of short-value answers: fill `correct` (yes/no) in manual_checks_todo.csv,
save it as manual_checks.csv in the same folder, and score again.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.core.llm import get_llm
from app.evaluation.harness import RUNS_DIR, RunConfig, run
from app.evaluation.metrics import score_run, write_details, write_report, write_scored
from app.retrieval.embeddings import get_embedder
from app.verification.nli import get_nli
from app.verification.verify import DEFAULT_THRESHOLD

DATASET = Path("eval/datasets/questions_v1.jsonl")


def score(run_dir: Path, dataset: Path) -> None:
    meta = json.loads((run_dir / "meta.json").read_text("utf-8"))
    scored, results = score_run(run_dir, dataset)
    write_scored(run_dir, scored)
    write_details(run_dir, dataset, scored)
    report = write_report(run_dir, results, meta)
    print(report.read_text("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    parser.add_argument("--variants", default="plain,temporal")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--no-claim-analysis", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args(argv)

    if args.score_only:
        if not args.run_id:
            parser.error("--score-only needs --run-id")
        score(RUNS_DIR / args.run_id, args.dataset)
        return 0

    if args.split == "test":
        print("Running on the held-out TEST split. Do this once, for final numbers only.")
    s = get_settings()
    variants = tuple(v.strip() for v in args.variants.split(",") if v.strip())
    run_id = args.run_id or f"{datetime.now(UTC):%Y%m%d-%H%M}-{args.split}-{'-'.join(variants)}"
    config = RunConfig(run_id, args.dataset, args.split, variants, s.corpus_repo_id,
                       limit=args.limit, threshold=args.threshold,
                       analyze_claims=not args.no_claim_analysis)  # fmt: skip
    with psycopg.connect(s.psycopg_dsn, autocommit=True) as conn:
        run_dir = run(conn, config, embedder=get_embedder(), llm=get_llm(), nli=get_nli(),
                      progress=print)  # fmt: skip
    print(f"run dir: {run_dir}\n")
    score(run_dir, args.dataset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
