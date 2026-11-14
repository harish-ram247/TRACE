# Evaluation run `dev-v1-plain-temporal`

- Split: **dev**, dataset `eval\datasets\questions_v1.jsonl` (sha256 `faf28b731181`)
- Model `gemini-3.5-flash-lite`, prompt `answer-v2`, embeddings `BAAI/bge-small-en-v1.5`, top_k 5
- Code commit `0213f4e017`
- Values: mean [95% bootstrap CI] (n). Small n means wide intervals; read them.

| Metric | plain | temporal |
|---|---|---|
| Answer accuracy (all) | 0.38 [0.27, 0.49] (n=78) | 0.67 [0.56, 0.77] (n=78) |
|   point-in-time | 0.03 [0.00, 0.08] (n=39) | 0.51 [0.36, 0.67] (n=39) |
|   current | 0.75 [0.50, 0.94] (n=16) | 0.88 [0.69, 1.00] (n=16) |
|   unanswerable | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) |
|   change | 0.00 [0.00, 0.00] (n=6) | 0.17 [0.00, 0.50] (n=6) |
| Stale-answer rate (lower is better) | 0.11 [0.04, 0.20] (n=55) | 0.02 [0.00, 0.05] (n=55) |
| Abstention recall (unanswerable -> NOT_FOUND) | 1.00 [1.00, 1.00] (n=17) | 1.00 [1.00, 1.00] (n=17) |
| Abstention precision | 0.29 [0.17, 0.41] (n=59) | 0.41 [0.27, 0.59] (n=41) |
| False abstention rate (lower is better) | 0.69 [0.57, 0.80] (n=61) | 0.39 [0.28, 0.51] (n=61) |
| Retrieval recall@k (gold version retrieved) | 0.38 [0.25, 0.51] (n=55) | 0.78 [0.67, 0.89] (n=55) |
| Wrong version at rank 1 (lower is better) | 0.09 [0.02, 0.18] (n=55) | 0.00 [0.00, 0.00] (n=55) |
| Cited the gold version, when correct | 0.54 [0.31, 0.77] (n=13) | 0.88 [0.76, 0.97] (n=34) |
| Temporal parse agreement | - | 1.00 [1.00, 1.00] (n=78) |
| Latency p50 / p95 ms (uncached calls) | 4952 / 7685 (n=78) | 5056 / 7240 (n=78) |
| Manual overrides applied | 0 | 0 |

## Temporal minus plain (paired, same questions)

Accuracy difference **+0.28** [95% CI +0.18, +0.38] over n=78 questions. Only temporal correct: 23; only plain correct: 1.

## Failure categories

**plain**

- F9 over-abstention, gold not retrieved: 24
- F9 over-abstention despite gold retrieved: 18
- F1 wrong version, answered with a stale value: 4
- F2 mixed versions in context, answered with a stale value: 2

**temporal**

- F9 over-abstention despite gold retrieved: 13
- F9 over-abstention, gold not retrieved: 11
- F1 wrong version, answered with a stale value: 1
- F5 generation error (gold retrieved, answer wrong or incomplete): 1

