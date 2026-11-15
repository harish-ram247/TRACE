# Evaluation run `dev-v1-verified-calibrated`

- Split: **dev**, dataset `eval\datasets\questions_v1.jsonl` (sha256 `faf28b731181`)
- Model `gemini-3.5-flash-lite`, prompt `answer-v3`, embeddings `BAAI/bge-small-en-v1.5`, top_k 5
- Code commit `4afaef582e`
- Values: mean [95% bootstrap CI] (n). Small n means wide intervals; read them.

| Metric | plain | plain_verified | temporal | temporal_verified |
|---|---|---|---|---|
| Answer accuracy (all) | 0.38 [0.27, 0.49] (n=78) | 0.36 [0.26, 0.46] (n=78) | 0.76 [0.65, 0.85] (n=78) | 0.73 [0.63, 0.82] (n=78) |
|   point-in-time | 0.03 [0.00, 0.08] (n=39) | 0.03 [0.00, 0.08] (n=39) | 0.72 [0.56, 0.85] (n=39) | 0.69 [0.54, 0.85] (n=39) |
|   current | 0.75 [0.50, 0.94] (n=16) | 0.62 [0.38, 0.88] (n=16) | 0.88 [0.69, 1.00] (n=16) | 0.81 [0.62, 1.00] (n=16) |
|   unanswerable | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) |
|   change | 0.00 [0.00, 0.00] (n=6) | 0.00 [0.00, 0.00] (n=6) | 0.00 [0.00, 0.00] (n=6) | 0.00 [0.00, 0.00] (n=6) |
| Stale-answer rate (lower is better) | 0.11 [0.04, 0.20] (n=55) | 0.11 [0.04, 0.20] (n=55) | 0.07 [0.02, 0.15] (n=55) | 0.07 [0.02, 0.15] (n=55) |
| Abstention recall (unanswerable -> NOT_FOUND) | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) |
| Abstention precision | 0.29 [0.17, 0.41] (n=59) | 0.28 [0.16, 0.39] (n=61) | 0.55 [0.39, 0.71] (n=31) | 0.52 [0.33, 0.70] (n=33) |
| False abstention rate (lower is better) | 0.69 [0.57, 0.80] (n=61) | 0.72 [0.61, 0.84] (n=61) | 0.23 [0.13, 0.34] (n=61) | 0.26 [0.15, 0.38] (n=61) |
| Retrieval recall@k (gold version retrieved) | 0.38 [0.25, 0.51] (n=55) | 0.38 [0.25, 0.51] (n=55) | 0.78 [0.67, 0.89] (n=55) | 0.78 [0.67, 0.89] (n=55) |
| Wrong version at rank 1 (lower is better) | 0.09 [0.02, 0.18] (n=55) | 0.09 [0.02, 0.18] (n=55) | 0.00 [0.00, 0.00] (n=55) | 0.00 [0.00, 0.00] (n=55) |
| Cited the gold version, when correct | 0.54 [0.31, 0.77] (n=13) | 0.64 [0.36, 0.91] (n=11) | 0.90 [0.81, 0.98] (n=42) | 1.00 [1.00, 1.00] (n=40) |
| Temporal parse agreement | - | - | 1.00 [1.00, 1.00] (n=78) | - |
| Latency p50 / p95 ms (uncached calls) | None / None (n=0) | 919 / 919 (n=2) | None / None (n=0) | 3216 / 3216 (n=2) |
| Manual overrides applied | 0 | 0 | 0 | 0 |
| Unsupported claims (lower is better) | 0.13 [0.03, 0.31] (n=30) | 0.00 [0.00, 0.00] (n=28) | 0.11 [0.05, 0.19] (n=70) | 0.00 [0.00, 0.00] (n=66) |
| Faithful but stale claims (lower is better) | 0.57 [0.32, 0.78] (n=30) | 0.64 [0.39, 0.86] (n=28) | 0.00 [0.00, 0.00] (n=70) | 0.00 [0.00, 0.00] (n=66) |
| Claims per answer | 1.58 | 1.65 | 1.49 | 1.47 |
| Verification actions | - | {'nothing_to_verify': 59, 'keep': 15, 'abstained': 2, 'revised': 2} | - | {'keep': 39, 'nothing_to_verify': 31, 'revised': 6, 'abstained': 2} |
| Claim extraction fallbacks | 0 | 0 | 0 | 0 |

## Temporal minus plain (paired, same questions)

Accuracy difference **+0.37** [95% CI +0.26, +0.49] over n=78 questions. Only temporal correct: 30; only plain correct: 1.

## Failure categories

**plain**

- F9 over-abstention, gold not retrieved: 24
- F9 over-abstention despite gold retrieved: 18
- F1 wrong version, answered with a stale value: 4
- F2 mixed versions in context, answered with a stale value: 2

**plain_verified**

- F9 over-abstention, gold not retrieved: 25
- F9 over-abstention despite gold retrieved: 19
- F1 wrong version, answered with a stale value: 4
- F2 mixed versions in context, answered with a stale value: 2

**temporal**

- F9 over-abstention, gold not retrieved: 9
- F9 over-abstention despite gold retrieved: 5
- F1 wrong version, answered with a stale value: 4
- F5 generation error (gold retrieved, answer wrong or incomplete): 1

**temporal_verified**

- F9 over-abstention, gold not retrieved: 9
- F9 over-abstention despite gold retrieved: 7
- F1 wrong version, answered with a stale value: 4
- F5 generation error (gold retrieved, answer wrong or incomplete): 1

