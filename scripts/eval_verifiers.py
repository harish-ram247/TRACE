"""Measure and calibrate claim verifiers against the labelled claim set (plan 10.4, Week 8).

Usage: python -m scripts.eval_verifiers [--verifiers xsmall,small,gemini]

Pairs: human-labelled claims ("yes" = supported; "unclear"/blank are skipped) plus the synthetic
negatives (value_swap, wrong_source). Every pair is scored by each verifier; scores are cached in
eval/reports/verifier_scores.jsonl so re-running is free.

The threshold is chosen on the "calib" split only, maximising balanced accuracy (mean of the
acceptance rate on positives and the rejection rate on negatives). Everything reported is
measured on the "eval" split. Results: eval/reports/verifier_calibration.{json,md}
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from app.core.llm import LLMError, get_llm
from app.verification.nli import OnnxNLI, entailment_against_chunk, get_nli

CANDIDATES = Path("eval/datasets/claims_v1_candidates.jsonl")
NEGATIVES = Path("eval/datasets/claims_v1_negatives.jsonl")
LABELS = Path("eval/datasets/review/claims_labeling.csv")
SCORES = Path("eval/reports/verifier_scores.jsonl")
REPORT = Path("eval/reports/verifier_calibration")

JUDGE_VERSION = "judge-v1"
JUDGE_SYSTEM = """\
You check claims against source texts from the Vite documentation.
For each item, decide whether the source text alone supports the claim: every part of the claim
must be stated or clearly implied by the source. The section heading is part of the source.
Formatting (backticks, quotes) does not matter. Do not use outside knowledge.
Return a JSON object only: {"results": [{"id": "...", "supported": true or false}]}"""


def load_pairs() -> list[dict]:
    with LABELS.open(encoding="utf-8-sig", newline="") as fh:
        labels = {r["id"]: r["supported"].strip().lower() for r in csv.DictReader(fh)}
    pairs = []
    for x in map(json.loads, CANDIDATES.read_text("utf-8").splitlines()):
        if labels.get(x["id"]) == "yes":
            pairs.append({**x, "label": 1, "kind": "human_yes"})
        elif labels.get(x["id"]) == "no":
            pairs.append({**x, "label": 0, "kind": "human_no"})
    for x in map(json.loads, NEGATIVES.read_text("utf-8").splitlines()):
        pairs.append({**x, "label": 0})
    return pairs


def premise(p: dict) -> str:
    return f"{p['section_path']}\n\n{p['source_text']}"  # same as verify.verify_claims


def score_nli(model, pairs: list[dict]) -> dict[str, float]:
    return {p["id"]: entailment_against_chunk(model, premise(p), [p["claim"]])[0]["entailment"]
            for p in pairs}  # fmt: skip


def score_judge(pairs: list[dict], batch: int = 8) -> dict[str, float]:
    llm = get_llm()
    out: dict[str, float] = {}
    for i in range(0, len(pairs), batch):
        chunk = pairs[i : i + batch]
        items = "\n\n".join(
            f'<item id="{p["id"]}">\n<source>\n{premise(p)}\n</source>\n'
            f"<claim>{p['claim']}</claim>\n</item>"
            for p in chunk
        )
        try:
            reply = llm.complete(
                [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": items}],
                json_mode=True,
                max_tokens=60 * len(chunk),
            )
            results = {r["id"]: bool(r["supported"]) for r in json.loads(reply.text)["results"]}
        except (LLMError, ValueError, KeyError, TypeError) as exc:
            print(f"  judge batch {i // batch} failed: {exc}")
            continue
        for p in chunk:
            if p["id"] in results:
                out[p["id"]] = 1.0 if results[p["id"]] else 0.0
    return out


def rates(pairs: list[dict], scores: dict[str, float], t: float) -> dict:
    def acc(sel, want):
        sel = [p for p in sel if p["id"] in scores]
        if not sel:
            return None
        return sum((scores[p["id"]] >= t) == want for p in sel) / len(sel), len(sel)

    pos = [p for p in pairs if p["label"] == 1]
    vs = [p for p in pairs if p["kind"] == "value_swap"]
    ws = [p for p in pairs if p["kind"] == "wrong_source"]
    out = {"threshold": t, "accept_true": acc(pos, True), "reject_value_swap": acc(vs, False),
           "reject_wrong_source": acc(ws, False)}  # fmt: skip
    parts = [v[0] for k, v in out.items() if k != "threshold" and v]
    out["balanced_accuracy"] = sum(parts) / len(parts) if parts else None
    return out


def calibrate(pairs: list[dict], scores: dict[str, float]) -> float:
    calib = [p for p in pairs if p["split"] == "calib"]
    candidates = sorted({round(scores[p["id"]], 4) for p in calib if p["id"] in scores} | {0.5})
    best = max(
        candidates, key=lambda t: (rates(calib, scores, t)["balanced_accuracy"] or 0, -abs(t - 0.5))
    )
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verifiers", default="xsmall,small,gemini")
    args = parser.parse_args(argv)
    pairs = load_pairs()
    cache: dict[tuple[str, str], float] = {}
    if SCORES.exists():
        for r in map(json.loads, SCORES.read_text("utf-8").splitlines()):
            cache[(r["verifier"], r["id"])] = r["score"]

    makers = {
        "xsmall": lambda ps: score_nli(get_nli(), ps),
        "small": lambda ps: score_nli(
            OnnxNLI("cross-encoder/nli-deberta-v3-small", "onnx/model_quint8_avx2.onnx"), ps
        ),
        "gemini": score_judge,
    }
    SCORES.parent.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in [v.strip() for v in args.verifiers.split(",") if v.strip()]:
        todo = [p for p in pairs if (name, p["id"]) not in cache]
        if todo:
            print(f"{name}: scoring {len(todo)} pairs")
            new = makers[name](todo)
            with SCORES.open("a", encoding="utf-8") as fh:
                for pid, sc in new.items():
                    cache[(name, pid)] = sc
                    fh.write(json.dumps({"verifier": name, "id": pid, "score": sc}) + "\n")
        scores = {pid: s for (v, pid), s in cache.items() if v == name}
        evaluation = [p for p in pairs if p["split"] == "eval"]
        t = calibrate(pairs, scores) if name != "gemini" else 0.5
        results[name] = {
            "calibrated_threshold": t,
            "eval_at_calibrated": rates(evaluation, scores, t),
            "eval_at_0.5": rates(evaluation, scores, 0.5),
            "scored": len(scores),
        }

    REPORT.with_suffix(".json").write_text(json.dumps(results, indent=1), "utf-8")
    lines = ["# Verifier calibration", "",
             f"Pairs: {sum(p['label'] == 1 for p in pairs)} human-labelled supported claims, "
             f"{sum(p['kind'] == 'value_swap' for p in pairs)} value-swap and "
             f"{sum(p['kind'] == 'wrong_source' for p in pairs)} wrong-source negatives. "
             "Threshold chosen on the calib split; numbers below are on the eval split.", "",
             "| Verifier | Threshold | Accepts true claims | Rejects value-swapped | "
             "Rejects wrong source | Balanced accuracy |", "|---|---|---|---|---|---|"]  # fmt: skip

    def cell(x):
        return f"{x[0]:.2f} (n={x[1]})" if x else "-"

    for name, r in results.items():
        for label, key in (("calibrated", "eval_at_calibrated"), ("0.5", "eval_at_0.5")):
            if name == "gemini" and label == "0.5":
                continue
            m = r[key]
            lines.append(
                f"| {name} ({label}) | {m['threshold']:.3f} | {cell(m['accept_true'])} | "
                f"{cell(m['reject_value_swap'])} | {cell(m['reject_wrong_source'])} | "
                f"{m['balanced_accuracy']:.2f} |"
            )
    REPORT.with_suffix(".md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
