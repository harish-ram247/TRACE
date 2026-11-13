"""Turn the reviewed CSV into the frozen evaluation dataset.

Usage: python -m scripts.finalize_questions [--allow-undecided]

Reads eval/datasets/review/questions_review.csv. For each row, `decision` must be:
  accept  keep as generated
  edit    keep, using the (edited) question / gold_answer / gold_tokens / stale_tokens columns
  reject  drop (write the reason in `note`)
Writes eval/datasets/questions_v1.jsonl with reviewed = true and the reviewer's note, and prints
the rejection rate. Once results have been computed on v1, do not change it; fix errors in a v2
and record why in docs/devlog.md (plan 10.3).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

CANDIDATES = Path("eval/datasets/questions_candidates.jsonl")
REVIEW = Path("eval/datasets/review/questions_review.csv")
OUT = Path("eval/datasets/questions_v1.jsonl")


def _tokens(cell: str) -> list[str]:
    return [t.strip() for t in cell.split("|") if t.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-undecided", action="store_true")
    args = parser.parse_args(argv)

    candidates = {
        q["id"]: q for q in map(json.loads, CANDIDATES.read_text("utf-8").splitlines()) if q
    }
    with REVIEW.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    decisions = Counter()
    kept = []
    undecided = []
    for row in rows:
        decision = row["decision"].strip().lower()
        decisions[decision or "undecided"] += 1
        if decision not in ("accept", "edit", "reject"):
            undecided.append(row["id"])
            continue
        if decision == "reject":
            continue
        q = dict(candidates[row["id"]])
        if decision == "edit":
            q["question"] = row["question"]
            q["gold_answer"] = row["gold_answer"]
            q["gold_tokens"] = _tokens(row["gold_tokens"])
            q["stale_tokens"] = _tokens(row["stale_tokens"])
        q["reviewed"] = True
        q["review_decision"] = decision
        q["review_note"] = row["note"].strip()
        kept.append(q)

    if undecided and not args.allow_undecided:
        print(f"{len(undecided)} rows have no decision (accept/edit/reject), e.g. {undecided[:3]}")
        return 1

    OUT.write_text("".join(json.dumps(q) + "\n" for q in kept), "utf-8")
    reviewed = sum(decisions[d] for d in ("accept", "edit", "reject"))
    rate = decisions["reject"] / reviewed if reviewed else 0
    print(f"decisions: {dict(decisions)} | rejection rate {rate:.0%}")
    print(f"kept {len(kept)}: {dict(Counter(q['type'] for q in kept))}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
