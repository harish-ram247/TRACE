# Devlog

Short weekly notes: what worked, what broke, what changed.

## Week 1

- Scaffolded repository, FastAPI app with `/health` and `/health/db`, Docker Compose (pgvector Postgres),
  Alembic, first migration (extensions, `documents`, versioned `chunks` with an exclusion constraint on
  overlapping validity), tests and CI workflow.

## Week 2

- Built the ingestion pipeline: git walker, markdown chunker, lineage matcher, ingestion service,
  `ingest_runs` migration, invariant checks and a CLI (`python -m app.ingest`).
- Tests: 47 total. The strongest is a seeded random-history test that rebuilds every historical state of a
  synthetic repo from the database and compares it with what git had at each commit.
- Smoke test on a real repository (28 first-parent commits): ingested in about 10 seconds, invariants hold.
  The smoke-test rows were deleted afterwards.
- Observed limitation: when a long section grows past the split threshold, its `[part N]` paths shift and
  later parts can be matched by similarity instead of by path. Acceptable for now; revisit after the real
  corpus is chosen.
- Not done: corpus choice (plan O1). The pipeline is corpus-agnostic, so it did not block this work.
- Later the same week: measured four candidate corpora (see `docs/corpus.md`) and chose the Vite docs.

## Week 3

- Pinned the Vite corpus and ingested it: 1688 commits, 3142 chunk versions, invariants ok (~6 min).
- Embeddings: fastembed with BAAI/bge-small-en-v1.5 (384-dim, ONNX, no PyTorch). Backfill of all 3142
  chunks took ~8.5 min on CPU. A hashing embedder stands in for tests so CI never downloads a model.
- Model download failed at first: Avast's HTTPS scanning re-signs traffic, and Python's bundled
  certificates do not trust its root. Fixed by using the Windows trust store (`truststore`), with
  verification still on.
- Hybrid retrieval: full-text (terms OR-ed, `ts_rank_cd`) plus HNSW vector search, fused with RRF,
  filtered by `valid @> as_of`.
- Filtered HNSW check (30 queries, 6 dates, top 20): recall 1.00 and 20 rows returned in every case,
  with and without iterative scan. At this corpus size (212 to 541 valid chunks per date) the filter is
  not a problem. Keep the check for larger corpora.
- 20-query retrieval smoke set (written by the assistant, needs your review), as of today's code:

  | Variant | R@1 | R@5 | R@10 | Wrong version at rank 1 |
  |---|---|---|---|---|
  | Hybrid, time filter | 0.50 | 0.85 | 0.85 | 0 |
  | Keyword only, time filter | 0.25 | 0.60 | 0.75 | 0 |
  | Vector only, time filter | 0.70 | 0.85 | 0.95 | 0 |
  | Hybrid, no BGE query prefix | 0.45 | 0.85 | 0.95 | 0 |
  | Hybrid, no time filter | 0.00 | 0.50 | 0.65 | 5 |

- Keyword ranking originally had no length normalisation, and long migration-guide sections won.
  Normalisation flag 2 raised keyword-only R@5 from 0.25 to 0.60 on this set. Chosen on 20 queries, so
  it must be re-checked on the held-out evaluation set.
- Vector-only beats hybrid at rank 1 on this set. Not tuned further: 20 queries is too few to choose
  fusion weights without overfitting.
