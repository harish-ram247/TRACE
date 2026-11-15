# Results

All numbers are from saved runs in `eval/runs/` and can be recomputed with
`python -m scripts.run_eval --score-only --run-id <id>`. Values are mean [95% bootstrap CI] (n).

## Verifier calibration (2026-11-15)

Labelled claim set: all 112 unique (claim, cited source) pairs from run `dev-v1-verified`, labelled by the
human reviewer with model scores hidden: 111 supported, 1 left blank (skipped), 0 unsupported. Because there
were no human "no" labels, negatives were built from the labelled claims with a known label:
42 **value-swapped** (the claim's value replaced by the same option's value from another docs version, checked
against the original source: the stale-value error TRACE must catch) and 109 **wrong-source** (claim paired
with an unrelated option's section). Thresholds were chosen on the calib split; numbers are on the eval split
(43 true claims, 13 value-swapped, 43 wrong-source). Details: `eval/reports/verifier_calibration.md`.

| Verifier | Accepts true claims | Rejects value-swapped | Rejects wrong source | Balanced accuracy |
|---|---|---|---|---|
| nli-deberta-v3-xsmall, threshold 0.5 | 0.67 | 1.00 | 1.00 | 0.89 |
| **nli-deberta-v3-xsmall, calibrated 0.027** | **0.95** | 0.92 | 0.91 | **0.93** |
| nli-deberta-v3-small, best threshold 0.79 | 0.72 | 0.92 | 1.00 | 0.88 |
| Gemini judge (`gemini-3.5-flash-lite`, batched) | 0.93 | 1.00 | 0.88 | 0.94 |

The 0.5 threshold was the problem, not the model: it rejected a third of true claims. The larger NLI model
did not help. The calibrated xsmall model matches the Gemini judge while being local, free and deterministic,
so it is the default (`DEFAULT_THRESHOLD = 0.027`). Caveats: 13 value-swapped claims in the eval split means
roughly +/-0.15 on that column; synthetic negatives are not human-labelled, and a few wrong-source pairs may be
loosely supported (two options that both default to `false`).

## Run `dev-v1-verified-calibrated` (2026-11-15), dev split: verification with the calibrated threshold

| Metric | Plain | Plain + verify | Temporal | Temporal + verify |
|---|---|---|---|---|
| Answer accuracy | 0.38 [0.27, 0.49] | 0.36 [0.26, 0.46] | **0.76 [0.65, 0.85]** | 0.73 [0.63, 0.82] |
| False abstention rate (lower is better) | 0.69 | 0.72 | **0.23** | 0.26 |
| Faithful-but-stale claims (lower is better) | 0.57 [0.32, 0.78] (30) | 0.64 [0.39, 0.86] (28) | **0.00 (70)** | **0.00 (66)** |
| Unsupported claims | 0.13 [0.03, 0.31] (30) | 0.00 (28) | 0.11 [0.05, 0.19] (70) | 0.00 (66) |
| Cited the gold version, when correct | 0.54 | 0.64 | 0.90 | **1.00** |
| Verification actions | - | keep 15, revised 2, abstained 2 | - | keep 39, revised 6, abstained 2 |

### What this shows

1. **Calibration removed most of the cost of verification**: temporal + verify loses 2 correct answers
   (0.76 -> 0.73) instead of 12 (0.60 before calibration). Both are verifier false rejections of correct claims
   ("`build.emptyOutDir` defaults to `true` if `outDir` is inside the project root" scored 0.005).
2. **Verification does not raise accuracy on this dataset.** Once retrieval is time-filtered, answers are
   already well supported (11% unsupported claims, mostly low-scoring correct ones), so there is little for
   verification to fix. Its benefits here are guarantees: every returned claim passed the check, and correct
   answers always cite the right version (1.00).
3. **The central result holds with the calibrated verifier**: 57% of plain RAG's claims are supported by an
   outdated source; entailment-only verification keeps them (64% of what remains); time filtering removes them
   (0.00).

## Run `dev-v1-verified` (2026-11-15), dev split: claim verification, uncalibrated

All four variants on the 78 dev questions. Same generation as `dev-v1-answer-v3` (answers came from the
cache); new: claim extraction (Gemini, JSON), entailment with `cross-encoder/nli-deberta-v3-xsmall`
(ONNX, quantised), threshold 0.5 (not yet calibrated), one revision allowed.

| Metric | Plain | Plain + verify | Temporal | Temporal + verify |
|---|---|---|---|---|
| Answer accuracy | 0.38 [0.27, 0.49] | 0.33 [0.23, 0.44] | **0.76 [0.65, 0.85]** | 0.60 [0.49, 0.71] |
| False abstention rate (lower is better) | 0.69 | 0.79 | **0.23** | 0.44 |
| Stale-answer rate (lower is better) | 0.11 | 0.07 | 0.07 | 0.07 |
| Faithful-but-stale claims (lower is better) | 0.47 [0.28, 0.66] (30) | 0.65 [0.38, 0.89] (17) | **0.00 (70)** | **0.00 (47)** |
| Unsupported claims (entailment < 0.5) | 0.37 [0.19, 0.58] (30) | 0.00 (17)\* | 0.39 [0.26, 0.52] (70) | 0.00 (47)\* |
| Cited the gold version, when correct | 0.54 | 0.56 | 0.90 | 1.00 |
| Verification actions | - | keep 10, revised 3, abstained 6 | - | keep 27, revised 6, dropped claims 1, abstained 13 |
| Latency p50 (uncached) | - | ~10.0 s | - | ~9.6 s |

\* By construction: verified variants only return claims that passed the check.

### What this shows

1. **A faithfulness check alone does not catch stale answers.** Almost half of plain RAG's claims (0.47)
   are fully supported by their cited source, but that source was outdated on the question's date. Adding
   entailment-only verification to plain RAG makes it worse (0.65 of the remaining claims), because it keeps
   exactly the well-supported but outdated ones. Both temporal variants have 0.00. This is the project's
   central claim, now measured: *faithful* and *current* are different properties.
2. **With the current entailment model, verification hurts accuracy** (temporal 0.76 -> 0.60). The model
   gives low scores to correct claims about markdown config entries: 24 of 59 claims in correct TRACE answers
   scored below 0.5 (14 below 0.1), for example "The default value for `build.target` is `'modules'`" scored
   0.04 against a source whose entry reads "Default: 'modules'". Verification then made 12 correct answers
   abstain and fixed none.
3. Claims in answers the checker marks wrong scored high (median 0.99); most of those are the known checker
   false negatives (correct Node.js answers listing dropped versions).
4. Verification roughly doubles latency (one extraction call, plus revision and re-extraction when needed).

### Next (Week 8)

Hand-label about 100 claims, measure the entailment model's precision and recall, calibrate the threshold on
half and report on the other half, and compare a second model (`nli-deberta-v3-small`) and an LLM judge. The
verification design stays; the scorer needs to be better before it can be trusted to drop answers.

## Run `dev-v1-answer-v3` (2026-11-14), dev split: current best

Same setup as the first run below, with prompt `answer-v3`: for questions about one point in time, the
resolved time phrase is removed from the question and the date is stated instead ("Before Vite 3, what did
`server.host` default to?" becomes "(about the documentation as of 2022-05-13) What did `server.host`
default to?"). The plain baseline is unchanged (its answers came from the response cache).

| Metric | Plain RAG (V0) | TRACE temporal (V1) |
|---|---|---|
| Answer accuracy (all) | 0.38 [0.27, 0.49] (78) | **0.76 [0.65, 0.85] (78)** |
| point-in-time | 0.03 [0.00, 0.08] (39) | 0.72 [0.56, 0.85] (39) |
| current | 0.75 [0.50, 0.94] (16) | 0.88 [0.69, 1.00] (16) |
| unanswerable | 1.00 (17) | 1.00 (17) |
| change | 0.00 (6) | 0.00 (6) |
| Stale-answer rate (lower is better) | 0.11 [0.04, 0.20] (55) | 0.07 [0.02, 0.15] (55) * |
| Abstention precision | 0.29 [0.17, 0.41] (59) | 0.55 [0.39, 0.71] (31) |
| False abstention rate (lower is better) | 0.69 [0.57, 0.80] (61) | 0.23 [0.13, 0.34] (61) |
| Retrieval recall@5 (gold version retrieved) | 0.38 [0.25, 0.51] (55) | 0.78 [0.67, 0.89] (55) |
| Wrong version at rank 1 (lower is better) | 0.09 [0.02, 0.18] (55) | 0.00 (55) |
| Cited the gold version, when correct | 0.54 [0.31, 0.77] (13) | 0.90 [0.81, 0.98] (42) |
| Temporal parse agreement | - | 1.00 (78) |
| Latency p50 / p95 (ms, TRACE) | (cached) | 4814 / 5973 |

**Paired difference (TRACE minus plain): accuracy +0.37 [+0.26, +0.49]**; 30 questions only TRACE answered
correctly, 1 only plain.

Effect of `answer-v3` on TRACE (same questions, same retrieval):

| Time phrase | answer-v2 | answer-v3 |
|---|---|---|
| Vite version ("in Vite 5", "before Vite 4"), n = 18 | 2 correct, 15 NOT_FOUND | **10 correct, 4 NOT_FOUND** |
| Date, n = 21 | 18 correct | 18 correct |
| Now, n = 16 | 14 correct | 14 correct |
| Change, n = 6 | 1 correct | 0 correct |

8 questions became correct, 1 became wrong (a change question that now names only the new value).

\* Checker false negatives: 3 of the 4 "stale" TRACE answers are correct. They state the right Node.js
requirement and then list versions that were dropped ("Node.js 14, 16, 17 and 19 are no longer supported"),
which the token check counts as stale values. If a manual check confirms them, TRACE accuracy is 0.79 and
the stale-answer rate 0.02. They are left unchanged above until checked by hand (`manual_checks.csv`).
The fourth is a real error: "before Vite 8, `build.target`" was answered from the CLI `--target` option.

Note: `answer-v3` was chosen after looking at dev results. That is what the dev split is for, but it means
dev numbers for v3 are optimistic; the test split has not been used and will give the unbiased number.

## Run `dev-v1-plain-temporal` (2026-11-14), dev split

Setup: 78 dev questions from `questions_v1.jsonl`, model `gemini-3.5-flash-lite`, prompt `answer-v2`,
embeddings `BAAI/bge-small-en-v1.5`, top 5 chunks, corpus pinned at Vite `4db98449`. The 39 test questions
were not used.

| Metric | Plain RAG (V0) | TRACE temporal (V1) |
|---|---|---|
| Answer accuracy (all) | 0.38 [0.27, 0.49] (78) | **0.67 [0.56, 0.77] (78)** |
| point-in-time | 0.03 [0.00, 0.08] (39) | 0.51 [0.36, 0.67] (39) |
| current | 0.75 [0.50, 0.94] (16) | 0.88 [0.69, 1.00] (16) |
| unanswerable | 1.00 (17) | 1.00 (17) |
| change | 0.00 (6) | 0.17 [0.00, 0.50] (6) |
| Stale-answer rate (lower is better) | 0.11 [0.04, 0.20] (55) | 0.02 [0.00, 0.05] (55) |
| Abstention precision | 0.29 [0.17, 0.41] (59) | 0.41 [0.27, 0.59] (41) |
| False abstention rate (lower is better) | 0.69 [0.57, 0.80] (61) | 0.39 [0.28, 0.51] (61) |
| Retrieval recall@5 (gold version retrieved) | 0.38 [0.25, 0.51] (55) | 0.78 [0.67, 0.89] (55) |
| Wrong version at rank 1 (lower is better) | 0.09 [0.02, 0.18] (55) | 0.00 (55) |
| Cited the gold version, when correct | 0.54 [0.31, 0.77] (13) | 0.88 [0.76, 0.97] (34) |
| Temporal parse agreement | - | 1.00 (78) |
| Latency p50 / p95 (ms) | 4952 / 7685 | 5056 / 7240 |

**Paired difference (TRACE minus plain, same 78 questions): accuracy +0.28 [+0.18, +0.38].** 23 questions
only TRACE answered correctly, 1 only plain did.

### By how the question states the time (answerable questions only)

| Time phrase | n | Plain correct | TRACE correct | TRACE answered NOT_FOUND |
|---|---|---|---|---|
| Date ("in June 2023", "in 2022", "on May 3, 2024") | 21 | 0.00 | **0.86** | 0.14 |
| Now | 16 | 0.75 | 0.88 | 0.12 |
| Vite version ("in Vite 5", "before Vite 4") | 18 | 0.06 | **0.11** | 0.83 |
| Change ("between X and Y") | 6 | 0.00 | 0.17 | 0.67 |

### What this shows

1. **Time filtering works where the date is explicit.** For date-phrased questions TRACE goes from 0.00 to
   0.86, retrieval of the right version doubles (0.38 to 0.78), and the wrong version is never ranked first.
2. **The main remaining failure is over-abstention on version-phrased questions.** The parser resolves them
   correctly (parse agreement 1.00) and the right version is often retrieved, but the model answers
   `NOT_FOUND`, apparently because the sources do not mention the version named in the question. Prompt
   `answer-v2` (which says the time phrase was already resolved) did not fix this.
3. **Plain RAG mostly refuses.** With every version in context it answers `NOT_FOUND` 69% of the time on
   answerable questions. Its perfect unanswerable score is therefore not a strength: abstention precision is
   only 0.29.
4. **Stale answers drop** from 0.11 to 0.02.
5. Latency is dominated by the LLM (about 5 s); retrieval adds tens of milliseconds.

### Caveats

- Dev split only, with n between 6 and 78 per cell; the intervals are wide and the change row (n = 6) says
  little. Final numbers come from the held-out test split, run once.
- Questions come from templates (see `docs/devlog.md`, Week 5), so phrasing is less varied than real use.
- 116 of 117 dataset decisions were confirmed assistant suggestions rather than individual human checks.
- The 30 short-value answers have not been hand-checked yet (`manual_checks_todo.csv`); 0 overrides applied.
- One known checker false negative: "In Vite 5, which Node.js versions…" was answered correctly ("18 or
  20+") but also mentioned versions that were dropped ("no longer supports 14, 16"), which the token check
  counts as stale.
- One model, one run; temperature 0 and the response cache make re-runs identical, so run-to-run variance is
  not measured.
