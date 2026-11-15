"""Build negative claim-source pairs whose label ("not supported") is known by construction.

Usage: python -m scripts.build_claim_negatives

The human labels (claims_labeling.csv) are almost all "supported": claims come from answers
written from those very sources. To measure how often a verifier wrongly ACCEPTS a claim, we
need negatives. Two kinds, both derived from human-labelled positives:

  value_swap    the claim's value replaced by the same option's value from another version of
                the docs, checked against the original source (e.g. "default port is 3000"
                against a source saying 5173). This is the stale-value error TRACE must catch.
  wrong_source  the claim paired with the source of an unrelated option.

A negative inherits the calib/eval split of the claim it came from, so calibration and
reporting never share a claim. Output: eval/datasets/claims_v1_negatives.jsonl
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.evaluation.facts import contains_token, mine_facts

CANDIDATES = Path("eval/datasets/claims_v1_candidates.jsonl")
LABELS = Path("eval/datasets/review/claims_labeling.csv")
OUT = Path("eval/datasets/claims_v1_negatives.jsonl")


def _option(section_path: str) -> str:
    return section_path.split(" > ")[-1].split(" [part")[0].strip().strip("`")


def _forms(value: str) -> list[str]:
    """Ways a value appears in a claim, most specific first."""
    return [f"`'{value}'`", f"'{value}'", f"`{value}`", value]


def value_swap(claim: str, current: str, other: str) -> str | None:
    for form in _forms(current):
        if form in claim:
            replacement = form.replace(current, other)
            return claim.replace(form, replacement, 1)
    return None


def main() -> int:
    positives = {
        x["id"]: x for x in map(json.loads, CANDIDATES.read_text("utf-8").splitlines()) if x
    }
    with LABELS.open(encoding="utf-8-sig", newline="") as fh:
        labels = {r["id"]: r["supported"].strip().lower() for r in csv.DictReader(fh)}
    positives = {k: v for k, v in positives.items() if labels.get(k) == "yes"}

    s = get_settings()
    with psycopg.connect(s.psycopg_dsn) as conn:
        facts = {f.subject: f for f in mine_facts(conn, s.corpus_repo_id)}

    negatives = []
    for pid, p in sorted(positives.items()):
        fact = facts.get(_option(p["section_path"]))
        if fact is None and "Node.js" in p["claim"]:
            fact = facts.get("Node.js")
        if fact is None or not fact.changed:
            continue
        values = [sp.core for sp in fact.spans]
        current = next((v for v in values if v and contains_token(p["claim"], v.strip("'"))), None)
        others = [v for v in dict.fromkeys(values) if v != current]
        if current is None or not others:
            continue
        for other in others:
            if contains_token(p["source_text"], other.strip("'")):
                continue  # the source also mentions the other value: label would be unclear
            swapped = value_swap(p["claim"], current, other)
            if swapped and swapped != p["claim"]:
                negatives.append({**p, "id": f"n_vs_{pid}", "kind": "value_swap",
                                  "claim": swapped, "from": pid, "label": "no"})  # fmt: skip
                break

    by_option: dict[str, list[dict]] = {}
    for p in positives.values():
        by_option.setdefault(_option(p["section_path"]), []).append(p)
    options = sorted(by_option)
    for pid, p in sorted(positives.items()):
        h = int(hashlib.sha256(pid.encode()).hexdigest(), 16)
        own = _option(p["section_path"])
        candidates = [o for o in options if o != own]
        other = by_option[candidates[h % len(candidates)]][0]
        values = [t for t in p["claim"].replace("`", " ").split() if any(ch.isdigit() for ch in t)]
        if any(contains_token(other["source_text"], v.strip(".,'")) for v in values):
            continue
        negatives.append({
            **p, "id": f"n_ws_{pid}", "kind": "wrong_source", "from": pid, "label": "no",
            "chunk_id": other["chunk_id"], "source_path": other["source_path"],
            "section_path": other["section_path"], "source_text": other["source_text"],
        })  # fmt: skip

    OUT.write_text("".join(json.dumps(n) + "\n" for n in negatives), "utf-8")
    print(f"{len(negatives)} negatives: {dict(Counter(n['kind'] for n in negatives))}")
    print("by split:", dict(Counter((n["kind"], n["split"]) for n in negatives)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
