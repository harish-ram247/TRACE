# Decisions

Record each decision with the date, the choice, the reason and the trade-off.

## Fixed at project start

See D1 to D8 in [project_plan.md](../project_plan.md) section 5.2.

## Log

| Date | Decision | Reason | Trade-off |
|---|---|---|---|
| 2026-11-13 | Host port 5433 for the Compose Postgres | Avoid clashing with a locally installed Postgres on 5432 | Tests and `.env` must use 5433 locally |
| 2026-11-13 | Migrations written as explicit SQL, no ORM models yet | Range types, exclusion constraints and pgvector are clearest in SQL | No autogenerate; models added when queries need them |
| 2026-11-13 | `lineage_id_seq` sequence instead of a lineages table | Keeps the schema minimal until lineage matching needs more | May add a lineages table later |
| 2026-11-13 | `chunks.embedding` nullable, `vector(384)` | Embedding model not chosen yet (plan O4) | Needs a migration if the dimension changes |
| 2026-11-13 | Read git through the `git` CLI via `subprocess`, not GitPython | No extra dependency, exact control over `-z` output and rename detection | Requires `git` on PATH |
| 2026-11-13 | First-parent history only (plan O2) | A merge is one event with a well-defined before and after; avoids replaying side-branch commits out of order | Commits inside merged feature branches are not individually versioned |
| 2026-11-13 | Ingestion uses synchronous psycopg, serving uses asyncpg | Ingestion is a batch job; sync is simpler and easier to test inside a rolled-back transaction | Two drivers in the project |
| 2026-11-13 | Effective commit time = max(commit time, previous effective time) | Validity must never run backwards when clocks or rebases make dates non-monotonic | Intervals can be slightly off for out-of-order commits |
| 2026-11-13 | A version that would be valid for zero time is not stored | Two commits with the same timestamp cannot both be "current" at any instant; empty ranges violate the schema | Intermediate draft is invisible to queries |
| 2026-11-13 | Per-commit transaction plus progress marker in `ingest_runs` | Crash-safe resume and idempotent re-runs | One transaction per commit, slower than batching |
| 2026-11-13 | Content hash ignores whitespace; front matter dropped | Reformatting is not a factual change | Whitespace-only edits to code blocks are not versioned |
| 2026-11-13 | Similarity threshold 0.8 for matching moved or renamed sections | Reasonable starting point | A section renamed and heavily rewritten in one commit starts a new lineage. Tune on the real corpus |
| 2026-11-13 | Corpus: Vite docs, `docs/` minus `docs/blog/`, pinned to `4db98449` (plan O1) | See `docs/corpus.md` | Single corpus; config split in 2022 breaks some lineages across files |
| 2026-11-13 | Embeddings via fastembed (ONNX) with BAAI/bge-small-en-v1.5 (plan O4, provisional) | No PyTorch, small download (~67 MB), fits a small server later, matches `vector(384)` | Second model not compared yet |
| 2026-11-13 | Embed `section_path + text`, store `embedding_model` per chunk | Heading trail adds context; model column makes a future model migration safe | Changing headings changes embeddings |
| 2026-11-13 | BGE query instruction prefix on queries only | Model card recommendation; no clear difference on the 20-query set | Revisit on the evaluation set |
| 2026-11-13 | Keyword branch ORs query terms and uses `ts_rank_cd` normalisation 2 | AND-ed natural-language questions rarely match; length normalisation stops long sections dominating | Tuned on 20 queries only |
| 2026-11-13 | RRF with k = 60, equal weights | Standard default | Vector-only is better at rank 1 on the dev set; weights not tuned yet |
| 2026-11-13 | Use the OS certificate store (`truststore`) for model downloads | Machines with TLS inspection (antivirus, corporate proxies) fail with Python's bundled certificates | Adds a dependency |
| 2026-11-13 | A path freed by a deleted file is archived (`#deleted@sha`) when another file is renamed onto it | Keeps history while respecting the unique path constraint | Archived paths look odd in `documents` |
