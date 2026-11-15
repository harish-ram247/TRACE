"""Build the claim-labelling sheet for verifier calibration (plan 10.4, Week 8).

Usage: python -m scripts.build_claim_labels [--run dev-v1-verified]

Collects every unique (claim, cited source chunk) pair from a run, with the full source text,
and writes:
  eval/datasets/claims_v1_candidates.jsonl   all pairs, with hidden fields (model scores, run,
                                             question id) used later for analysis
  eval/datasets/review/claims_labeling.csv   the sheet a person labels, without model scores

Each pair is assigned to "calib" (used to choose thresholds) or "eval" (used only to report
accuracy) by a hash of the claim, about half each.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import psycopg

from app.core.config import get_settings

OUT = Path("eval/datasets/claims_v1_candidates.jsonl")
SHEET = Path("eval/datasets/review/claims_labeling.csv")


def _split(text: str) -> str:
    return "calib" if int(hashlib.sha256(text.encode()).hexdigest(), 16) % 2 == 0 else "eval"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="dev-v1-verified")
    args = parser.parse_args(argv)
    run_dir = Path("eval/runs") / args.run

    pairs: dict[tuple[str, int], dict] = {}
    for line in (run_dir / "outputs.jsonl").read_text("utf-8").splitlines():
        rec = json.loads(line)
        verification = rec.get("verification") or {}
        pool = list(rec.get("final_claims") or [])
        pool += verification.get("verdicts", []) + verification.get("revised_verdicts", [])
        for c in pool:
            if c.get("best_chunk_id") is None:
                continue
            key = (c["text"], c["best_chunk_id"])
            pairs.setdefault(key, {
                "claim": c["text"], "chunk_id": c["best_chunk_id"],
                "xsmall_entailment": c["entailment"], "xsmall_contradiction": c["contradiction"],
                "question_id": rec["question_id"], "variant": rec["variant"], "run": args.run,
            })  # fmt: skip

    s = get_settings()
    with psycopg.connect(s.psycopg_dsn) as conn:
        for p in pairs.values():
            row = conn.execute(
                """
                SELECT d.source_path, c.section_path, c.text FROM chunks c
                JOIN documents d ON d.id = c.document_id WHERE c.id = %s
                """,
                (p["chunk_id"],),
            ).fetchone()
            p["source_path"], p["section_path"], p["source_text"] = row

    items = sorted(pairs.values(), key=lambda p: hashlib.sha1(p["claim"].encode()).hexdigest())
    for i, p in enumerate(items, start=1):
        p["id"] = f"c{i:03d}"
        p["split"] = _split(p["claim"])

    OUT.write_text("".join(json.dumps(p) + "\n" for p in items), "utf-8")
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    with SHEET.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "supported", "note", "claim", "source", "source_text"])
        for p in items:
            source = f"{p['source_path']} | {p['section_path']}"
            w.writerow([p["id"], "", "", p["claim"], source, " ".join(p["source_text"].split())])
    print(f"{len(items)} claim-source pairs | split: {dict(Counter(p['split'] for p in items))}")
    print(f"wrote {OUT} and {SHEET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
