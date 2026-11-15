"""Score saved run outputs (plan section 10.5) and classify failures (10.7).

Everything here works on the files a run saved; nothing calls the model or the database.

Per question and variant:
- correct          answer passes the token check (or a manual override says so)
- stale            answer contains a value that was only true at another time
- abstained        the system answered NOT_FOUND
- gold_retrieved   the chunk version valid at the question's date is among the retrieved chunks
                   (matched by file, section and validity, not database id, so re-ingesting the
                   corpus does not break old runs)
- wrong_version_1  rank 1 is the right section but a version not valid at the question's date

Aggregates carry 95% bootstrap confidence intervals (percentile method, fixed seed). The
difference between two variants uses a paired bootstrap over the same questions.
"""

from __future__ import annotations

import csv
import json
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.evaluation.facts import check_answer, contains_token

BOOTSTRAP_SAMPLES = 2000
SEED = 13


@dataclass
class Scored:
    question_id: str
    variant: str
    type: str
    answerable: bool
    correct: bool
    auto_correct: bool
    manual: bool
    stale: bool
    abstained: bool
    gold_retrieved: bool | None
    wrong_version_1: bool | None
    cited_gold: bool | None
    parse_ok: bool | None
    category: str | None
    latency_ms: int
    generation_ms: int
    cached: bool
    n_claims: int = 0
    n_unsupported: int = 0
    n_faithful_stale: int = 0
    action: str | None = None
    extraction_method: str | None = None


def _in_range(when: datetime, start: str, end: str | None) -> bool:
    return datetime.fromisoformat(start) <= when and (
        end is None or when < datetime.fromisoformat(end)
    )


def _is_gold(hit: dict, ref: dict, when: datetime) -> bool:
    return (
        hit["source_path"] == ref["source_path"]
        and hit["section_path"] == ref["section_path"]
        and _in_range(when, hit["valid_from"], hit["valid_until"])
    )


def _same_section(hit: dict, ref: dict) -> bool:
    return hit["source_path"] == ref["source_path"] and hit["section_path"] == ref["section_path"]


def load_manual(path: Path) -> dict[tuple[str, str], bool]:
    """manual_checks.csv: question_id, variant, correct (yes/no), note."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        verdict = r.get("correct", "").strip().lower()
        if verdict in ("yes", "no"):
            out[(r["question_id"], r["variant"])] = verdict == "yes"
    return out


def _claim_counts(q: dict, rec: dict, threshold: float) -> tuple[int, int, int]:
    """(claims, unsupported, faithful but stale) for the answer as finally returned.

    Validity is judged against the dataset's as-of date, not the parsed one, so every variant is
    held to the same truth.
    """
    claims = rec.get("final_claims") or []
    as_of = datetime.fromisoformat(q["as_of"])
    unsupported = stale = 0
    for c in claims:
        if c["entailment"] < threshold:
            unsupported += 1
        elif c["best_valid_from"] and not _in_range(
            as_of, c["best_valid_from"], c["best_valid_until"]
        ):
            stale += 1
    return len(claims), unsupported, stale


def score_record(
    q: dict, rec: dict, manual: dict[tuple[str, str], bool], threshold: float = 0.5
) -> Scored:
    answer = rec["answer"]
    auto = check_answer(answer, q["gold_tokens"], q["stale_tokens"], q["answerable"])
    key = (q["id"], rec["variant"])
    correct = manual.get(key, auto)
    abstained = bool(rec["not_found"])
    stale = (
        q["answerable"]
        and not abstained
        and any(contains_token(answer, t) for t in q["stale_tokens"])
    )

    as_of = datetime.fromisoformat(q["as_of"])
    hits = rec["hits"]
    gold_retrieved = wrong_version_1 = cited_gold = None
    if q["answerable"] and q["type"] != "change" and q["gold_refs"]:
        ref = q["gold_refs"][-1]
        gold_retrieved = any(_is_gold(h, ref, as_of) for h in hits)
        wrong_version_1 = (
            bool(hits) and _same_section(hits[0], ref) and not _is_gold(hits[0], ref, as_of)
        )
        cited = [h for h in hits if h["chunk_id"] in set(rec["cited_chunk_ids"])]
        cited_gold = any(_is_gold(h, ref, as_of) for h in cited)

    parse_ok = None
    if rec["variant"] == "temporal" and rec["time"]:
        parse_ok = datetime.fromisoformat(rec["time"]["as_of"]) == as_of

    category = None
    if not correct:
        category = categorise(q, rec, stale, abstained, gold_retrieved, parse_ok)

    timings = rec.get("timings_ms") or {}
    n_claims, n_unsupported, n_stale = _claim_counts(q, rec, threshold)
    return Scored(
        question_id=q["id"],
        variant=rec["variant"],
        type=q["type"],
        answerable=q["answerable"],
        correct=correct,
        auto_correct=auto,
        manual=key in manual,
        stale=stale,
        abstained=abstained,
        gold_retrieved=gold_retrieved,
        wrong_version_1=wrong_version_1,
        cited_gold=cited_gold,
        parse_ok=parse_ok,
        category=category,
        latency_ms=sum(timings.values()),
        generation_ms=timings.get("generation", 0),
        cached=bool(rec.get("cached")),
        n_claims=n_claims,
        n_unsupported=n_unsupported,
        n_faithful_stale=n_stale,
        action=(rec.get("verification") or {}).get("action"),
        extraction_method=(rec.get("verification") or {}).get("extraction_method"),
    )


def categorise(q, rec, stale, abstained, gold_retrieved, parse_ok) -> str:
    """Failure taxonomy (project_plan.md appendix A)."""
    if not q["answerable"]:
        return "F10 under-abstention (answered an unanswerable question)"
    if parse_ok is False:
        return "F3 temporal parse error"
    if abstained:
        if gold_retrieved is False:
            return "F9 over-abstention, gold not retrieved"
        return "F9 over-abstention despite gold retrieved"
    if stale:
        ref = q["gold_refs"][-1] if q["gold_refs"] else None
        versions = [h for h in rec["hits"] if ref and _same_section(h, ref)]
        if len(versions) > 1:
            return "F2 mixed versions in context, answered with a stale value"
        return "F1 wrong version, answered with a stale value"
    if gold_retrieved is False:
        return "F4 retrieval miss"
    if rec["invalid_citations"]:
        return "F7 citation error"
    return "F5 generation error (gold retrieved, answer wrong or incomplete)"


# ---------------------------------------------------------------------------- aggregation
def _ci(values: list[float], rng: random.Random) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    n = len(values)
    means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAP_SAMPLES)
    )
    return means[int(0.025 * BOOTSTRAP_SAMPLES)], means[int(0.975 * BOOTSTRAP_SAMPLES) - 1]


def _rate(items: list[Scored], pred, rng: random.Random) -> dict:
    values = [1.0 if pred(s) else 0.0 for s in items]
    if not values:
        return {"n": 0, "value": None, "ci": None}
    lo, hi = _ci(values, rng)
    return {"n": len(values), "value": sum(values) / len(values), "ci": [lo, hi]}


def _pct(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def answerable_claims(items: list[Scored]) -> list[Scored]:
    return [s for s in items if s.answerable and s.n_claims]


def _ratio(items: list[Scored], field: str, rng: random.Random) -> dict:
    """Pooled claim-level rate; bootstrap over questions (an answer's claims move together)."""
    if not items:
        return {"n": 0, "value": None, "ci": None}
    num = [getattr(s, field) for s in items]
    den = [s.n_claims for s in items]
    n = len(items)
    samples = []
    for _ in range(BOOTSTRAP_SAMPLES):
        idx = [rng.randrange(n) for _ in range(n)]
        d = sum(den[i] for i in idx)
        samples.append(sum(num[i] for i in idx) / d if d else 0.0)
    samples.sort()
    lo = samples[int(0.025 * BOOTSTRAP_SAMPLES)]
    hi = samples[int(0.975 * BOOTSTRAP_SAMPLES) - 1]
    return {"n": sum(den), "value": sum(num) / sum(den), "ci": [lo, hi]}


def aggregate(scored: list[Scored]) -> dict:
    by_variant: dict[str, list[Scored]] = defaultdict(list)
    for s in scored:
        by_variant[s.variant].append(s)

    results: dict = {"variants": {}}
    for variant, items in sorted(by_variant.items()):
        rng = random.Random(SEED)
        answerable = [s for s in items if s.answerable]
        factual = [s for s in answerable if s.type in ("point_in_time", "current")]
        unanswerable = [s for s in items if not s.answerable]
        abstentions = [s for s in items if s.abstained]
        retrievable = [s for s in items if s.gold_retrieved is not None]
        live = [s for s in items if not s.cached]
        results["variants"][variant] = {
            "n": len(items),
            "accuracy": _rate(items, lambda s: s.correct, rng),
            "accuracy_by_type": {
                t: _rate([s for s in items if s.type == t], lambda s: s.correct, rng)
                for t in ("point_in_time", "current", "unanswerable", "change")
            },
            "stale_answer_rate": _rate(factual, lambda s: s.stale, rng),
            "abstention_recall": _rate(unanswerable, lambda s: s.abstained, rng),
            "abstention_precision": _rate(abstentions, lambda s: not s.answerable, rng),
            "false_abstention_rate": _rate(answerable, lambda s: s.abstained, rng),
            "retrieval_recall_at_k": _rate(retrievable, lambda s: s.gold_retrieved, rng),
            "wrong_version_at_rank_1": _rate(retrievable, lambda s: s.wrong_version_1, rng),
            "cited_gold_when_correct": _rate(
                [s for s in retrievable if s.correct], lambda s: s.cited_gold, rng
            ),
            "parse_agreement": _rate(
                [s for s in items if s.parse_ok is not None], lambda s: s.parse_ok, rng
            ),
            "latency_ms": {
                "p50": _pct([s.latency_ms for s in live], 0.5),
                "p95": _pct([s.latency_ms for s in live], 0.95),
                "measured_on": len(live),
            },
            "manual_overrides": sum(s.manual for s in items),
            "unsupported_claim_rate": _ratio(
                [s for s in answerable_claims(items)], "n_unsupported", rng
            ),
            "faithful_but_stale_rate": _ratio(
                [s for s in answerable_claims(items)], "n_faithful_stale", rng
            ),
            "claims_per_answer": (
                round(
                    sum(s.n_claims for s in items) / max(1, sum(1 for s in items if s.n_claims)), 2
                )
            ),
            "verification_actions": dict(Counter(s.action for s in items if s.action)),
            "extraction_fallbacks": sum(
                1 for s in items if s.extraction_method == "sentence_fallback"
            ),
            "failure_categories": dict(Counter(s.category for s in items if s.category)),
        }

    variants = sorted(by_variant)
    if "plain" in variants and "temporal" in variants:
        results["paired"] = paired_difference(by_variant["plain"], by_variant["temporal"])
    return results


def paired_difference(a: list[Scored], b: list[Scored]) -> dict:
    """Accuracy of b minus a over questions both variants answered, paired bootstrap."""
    a_by = {s.question_id: s.correct for s in a}
    b_by = {s.question_id: s.correct for s in b}
    ids = sorted(set(a_by) & set(b_by))
    if not ids:
        return {}
    diffs = [float(b_by[i]) - float(a_by[i]) for i in ids]
    lo, hi = _ci(diffs, random.Random(SEED))
    return {
        "n": len(ids),
        "accuracy_difference": statistics.fmean(diffs),
        "ci": [lo, hi],
        "only_b_correct": sum(1 for d in diffs if d > 0),
        "only_a_correct": sum(1 for d in diffs if d < 0),
    }


# ---------------------------------------------------------------------------- files
def score_run(
    run_dir: Path, dataset: Path, threshold: float | None = None
) -> tuple[list[Scored], dict]:
    questions = {
        q["id"]: q
        for q in (json.loads(x) for x in dataset.read_text("utf-8").splitlines() if x.strip())
    }
    manual = load_manual(run_dir / "manual_checks.csv")
    records = [
        json.loads(x) for x in (run_dir / "outputs.jsonl").read_text("utf-8").splitlines() if x
    ]
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    t = threshold if threshold is not None else meta.get("threshold") or 0.5
    scored = [score_record(questions[r["question_id"]], r, manual, t) for r in records]
    return scored, aggregate(scored)


def write_details(run_dir: Path, dataset: Path, scored: list[Scored]) -> None:
    """failures.csv for error analysis, manual_checks_todo.csv for short-value answers."""
    questions = {
        q["id"]: q
        for q in (json.loads(x) for x in dataset.read_text("utf-8").splitlines() if x.strip())
    }
    records = {
        (r["question_id"], r["variant"]): r
        for r in (
            json.loads(x) for x in (run_dir / "outputs.jsonl").read_text("utf-8").splitlines() if x
        )
    }
    with (run_dir / "failures.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["question_id", "variant", "category", "type", "question", "as_of",
                    "gold_answer", "answer", "gold_retrieved", "parsed_as_of"])  # fmt: skip
        for s in scored:
            if s.correct:
                continue
            q, r = questions[s.question_id], records[(s.question_id, s.variant)]
            parsed = r["time"]["as_of"][:10] if r["time"] else ""
            w.writerow([s.question_id, s.variant, s.category, q["type"], q["question"],
                        q["as_of"][:10], q["gold_answer"], r["answer"], s.gold_retrieved,
                        parsed])  # fmt: skip

    todo = run_dir / "manual_checks_todo.csv"
    with todo.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["question_id", "variant", "correct", "note", "auto_correct", "question",
                    "as_of", "gold_answer", "answer"])  # fmt: skip
        for s in scored:
            q = questions[s.question_id]
            if "short_value" in q.get("flags", []):
                r = records[(s.question_id, s.variant)]
                auto = "yes" if s.auto_correct else "no"
                row = [s.question_id, s.variant, "", "", auto]
                w.writerow(row + [q["question"], q["as_of"][:10], q["gold_answer"], r["answer"]])


def write_report(run_dir: Path, results: dict, meta: dict) -> Path:
    def fmt(m: dict | None) -> str:
        if not m or m.get("value") is None:
            return "-"
        lo, hi = m["ci"]
        return f"{m['value']:.2f} [{lo:.2f}, {hi:.2f}] (n={m['n']})"

    variants = results["variants"]
    names = list(variants)
    lines = [
        f"# Evaluation run `{meta['run_id']}`",
        "",
        f"- Split: **{meta['split']}**, dataset `{meta['dataset']}` "
        f"(sha256 `{meta['dataset_sha256'][:12]}`)",
        f"- Model `{meta['llm_model']}`, prompt `{meta['prompt_version']}`, "
        f"embeddings `{meta['embedding_model']}`, top_k {meta['top_k']}",
        f"- Code commit `{(meta.get('git_commit') or 'unknown')[:10]}`",
        "- Values: mean [95% bootstrap CI] (n). Small n means wide intervals; read them.",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    rows = [
        ("Answer accuracy (all)", lambda v: fmt(v["accuracy"])),
        ("  point-in-time", lambda v: fmt(v["accuracy_by_type"]["point_in_time"])),
        ("  current", lambda v: fmt(v["accuracy_by_type"]["current"])),
        ("  unanswerable", lambda v: fmt(v["accuracy_by_type"]["unanswerable"])),
        ("  change", lambda v: fmt(v["accuracy_by_type"]["change"])),
        ("Stale-answer rate (lower is better)", lambda v: fmt(v["stale_answer_rate"])),
        ("Abstention recall (unanswerable -> NOT_FOUND)", lambda v: fmt(v["abstention_recall"])),
        ("Abstention precision", lambda v: fmt(v["abstention_precision"])),
        ("False abstention rate (lower is better)", lambda v: fmt(v["false_abstention_rate"])),
        ("Retrieval recall@k (gold version retrieved)", lambda v: fmt(v["retrieval_recall_at_k"])),
        ("Wrong version at rank 1 (lower is better)", lambda v: fmt(v["wrong_version_at_rank_1"])),
        ("Cited the gold version, when correct", lambda v: fmt(v["cited_gold_when_correct"])),
        ("Temporal parse agreement", lambda v: fmt(v["parse_agreement"])),
        ("Latency p50 / p95 ms (uncached calls)",
         lambda v: f"{v['latency_ms']['p50']} / {v['latency_ms']['p95']} "
                   f"(n={v['latency_ms']['measured_on']})"),
        ("Manual overrides applied", lambda v: str(v["manual_overrides"])),
        ("Unsupported claims (lower is better)", lambda v: fmt(v.get("unsupported_claim_rate"))),
        ("Faithful but stale claims (lower is better)",
         lambda v: fmt(v.get("faithful_but_stale_rate"))),
        ("Claims per answer", lambda v: str(v.get("claims_per_answer"))),
        ("Verification actions", lambda v: str(v.get("verification_actions") or "-")),
        ("Claim extraction fallbacks", lambda v: str(v.get("extraction_fallbacks", 0))),
    ]  # fmt: skip
    for label, get in rows:
        lines.append(f"| {label} | " + " | ".join(get(variants[n]) for n in names) + " |")

    if paired := results.get("paired"):
        lo, hi = paired["ci"]
        lines += [
            "",
            "## Temporal minus plain (paired, same questions)",
            "",
            f"Accuracy difference **{paired['accuracy_difference']:+.2f}** "
            f"[95% CI {lo:+.2f}, {hi:+.2f}] over n={paired['n']} questions. "
            f"Only temporal correct: {paired['only_b_correct']}; "
            f"only plain correct: {paired['only_a_correct']}.",
        ]

    lines += ["", "## Failure categories", ""]
    for name in names:
        cats = variants[name]["failure_categories"]
        lines.append(f"**{name}**")
        lines.append("")
        for cat, n in sorted(cats.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {cat}: {n}")
        lines.append("")
    path = run_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", "utf-8")
    (run_dir / "results.json").write_text(json.dumps(results, indent=1), "utf-8")
    return path


def write_scored(run_dir: Path, scored: list[Scored]) -> None:
    (run_dir / "scored.jsonl").write_text(
        "".join(json.dumps(asdict(s)) + "\n" for s in scored), "utf-8"
    )
