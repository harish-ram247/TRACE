"""Build candidate evaluation questions and a review sheet (plan Week 5).

Usage: python -m scripts.build_questions [--seed 7]

Writes
  eval/datasets/questions_candidates.jsonl   all candidates (machine-readable)
  eval/datasets/review/questions_review.csv  one row per candidate, for a person to mark
                                             decision = accept / reject / edit, with a note

"now" for current questions is the pinned corpus commit date, so results do not drift as real
time passes. Every candidate's as_of is also run through the temporal parser; disagreements are
flagged (they would be parser bugs or generator bugs).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.evaluation.facts import contains_token, mine_facts
from app.evaluation.questions import generate
from app.temporal.parser import parse_time
from app.temporal.releases import load_prerelease_starts, load_releases

PINNED_NOW = datetime.fromisoformat("2026-11-13T08:17:32+00:00")  # corpus pin 4db98449
OUT = Path("eval/datasets/questions_candidates.jsonl")
REVIEW = Path("eval/datasets/review/questions_review.csv")
TARGETS = {"point_in_time": 60, "current": 30, "unanswerable": 30, "change": 20}


def _evidence(conn, chunk_id: int, gold: str) -> str:
    text = conn.execute("SELECT text FROM chunks WHERE id = %s", (chunk_id,)).fetchone()[0]
    flat = " ".join(text.split())
    at = max(flat.find("Default"), flat.find("Node.js"), 0)
    if gold and (i := flat.find(gold[:15])) >= 0:
        at = i
    return flat[max(0, at - 120) : at + 160]


def _verify(conn, repo_id: str, q) -> None:
    """Automatic sanity checks; results become flags for the reviewer."""
    if not q.answerable:
        subject = q.fact_key.split(":", 1)[1]
        n = conn.execute(
            """
            SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE d.repo_url = %s AND c.valid @> %s::timestamptz AND strpos(c.text, %s) > 0
            """,
            (repo_id, q.as_of, subject),
        ).fetchone()[0]
        q.flags = [f for f in q.flags if f != "verify_not_documented_elsewhere"]
        q.flags.append("verified_absent" if n == 0 else f"mentioned_elsewhere={n}")
        return
    for ref, when in zip(q.gold_refs, [q.range_start, q.as_of][-len(q.gold_refs) :], strict=True):
        text = conn.execute(
            """
            SELECT c.text FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE d.repo_url = %s AND d.source_path = %s AND c.section_path = %s
              AND c.valid @> %s::timestamptz
            """,
            (repo_id, ref["source_path"], ref["section_path"], when),
        ).fetchone()
        if text is None:
            q.flags.append("gold_section_not_valid_at_as_of")
        elif q.type != "change" and not all(contains_token(text[0], t) for t in q.gold_tokens):
            q.flags.append("gold_not_in_source")


def _select(candidates, rng: random.Random):
    by_type: dict[str, list] = {}
    for q in candidates:
        by_type.setdefault(q.type, []).append(q)
    chosen = []
    for qtype, target in TARGETS.items():
        pool = by_type.get(qtype, [])
        if qtype == "current":  # prefer facts that changed (they have stale distractors)
            pool = sorted(pool, key=lambda q: (not q.stale_tokens, rng.random()))
        else:
            rng.shuffle(pool)
        chosen += pool[:target]
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    s = get_settings()
    releases, pre = load_releases(), load_prerelease_starts()

    with psycopg.connect(s.psycopg_dsn) as conn:
        facts = mine_facts(conn, s.corpus_repo_id)
        candidates = generate(facts, PINNED_NOW, releases, pre, seed=args.seed)
        chosen = _select(candidates, random.Random(args.seed))

        disagreements = 0
        for q in chosen:
            parsed = parse_time(q.question, PINNED_NOW, releases=releases, prereleases=pre)
            if parsed.as_of != datetime.fromisoformat(q.as_of):
                q.flags.append(f"parser_as_of={parsed.as_of.isoformat()}")
                disagreements += 1
            if q.type == "change" and parsed.intent != "change":
                q.flags.append(f"parser_intent={parsed.intent}")
            _verify(conn, s.corpus_repo_id, q)

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("".join(json.dumps(q.to_json()) + "\n" for q in chosen), "utf-8")

        REVIEW.parent.mkdir(parents=True, exist_ok=True)
        with REVIEW.open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "decision", "note", "split", "type", "question", "as_of",
                        "gold_answer", "gold_tokens", "stale_tokens", "flags", "source",
                        "evidence"])  # fmt: skip
            for q in chosen:
                ref = q.gold_refs[-1] if q.gold_refs else None
                source = f"{ref['source_path']} | {ref['section_path']}" if ref else ""
                evidence = _evidence(conn, ref["chunk_id"], q.gold_answer) if ref else ""
                w.writerow([q.id, "", "", q.split, q.type, q.question, q.as_of[:10],
                            q.gold_answer, " | ".join(q.gold_tokens), " | ".join(q.stale_tokens),
                            "; ".join(q.flags), source, re.sub(r"\s+", " ", evidence)])  # fmt: skip

    changed = sum(f.changed for f in facts)
    print(f"facts: {len(facts)} ({changed} changed) | candidates: {len(candidates)}", end=" ")
    print(f"| chosen: {len(chosen)}")
    print("by type:", dict(Counter(q.type for q in chosen)))
    print("by split:", dict(Counter(q.split for q in chosen)))
    print("flagged:", sum(bool(q.flags) for q in chosen), "| parser disagreements:", disagreements)
    print(f"wrote {OUT} and {REVIEW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
