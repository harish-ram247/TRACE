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
| 2026-11-13 | LLM: free-tier hosted API via an OpenAI-compatible endpoint (plan O3); provider chosen in `.env` | Quality and speed without a GPU; same model for the deployed demo and the evaluation; one client covers most providers | Quotas and silent model updates: pin a model version, cache every response, record the model per run |
| 2026-11-13 | LLM model: `gemini-3.5-flash-lite` via Google's OpenAI-compatible endpoint, dedicated `TRACE` project on the free tier | Newest stable Flash-Lite; free-tier limits 15 RPM, 250K TPM, 500 RPD (AI Studio, 2026-11-13); JSON mode verified with `llm_check` | 500 requests/day bounds experiment size; client spaced to 12 RPM |
| 2026-11-13 | Time parsing by hand-written rules, no `dateparser` | Predictable, testable, no false matches on numbers like ports; LLM fallback only for vague phrases | Unusual phrasings fall back to "now" (flagged as assumed) |
| 2026-11-13 | Period -> instant: "in/as of/during/by P" = end of P; "before P" = just before start; "since/from" = start; "early/mid/late" = 1/6, 1/2, end; clamp to now | One documented convention for gold labels and the parser | "in 2023" means the state at the end of 2023 |
| 2026-11-13 | Bare years only 2010-2039, not after a letter or hyphenated digit | Avoids "es2020", "port 2000", ranges | A year written as "'23" is not recognised |
| 2026-11-13 | "in Vite N" = release date; "before Vite N" = just before N's first prerelease tag | Docs on main describe N during its prereleases (verified for v3) | Minor versions without prerelease tags use the release date |
| 2026-11-13 | Plain baseline prompt has no dates; temporal prompt shows as-of date and each source's validity | The baseline is "plain RAG", not "time-aware prompting" | A dates-in-prompt-without-filter variant could be added as an extra ablation |
| 2026-11-13 | Prompt `answer-v2`: names the resolved time phrase and says sources need not mention it | v1 answered NOT_FOUND when sources did not mention the version in the question | Prompt changes invalidate cached answers by design (cache key includes messages) |
| 2026-11-13 | Generation temperature 0, max 400 tokens, at most 4 sentences | Reproducible, cache-friendly, short cited answers | Less fluent answers |
| 2026-11-13 | Evaluation facts: config defaults and Node.js requirement, compared by core value | Gold answers extractable from the docs text without an LLM; cosmetic edits ignored | Narrow question style (defaults and versions) |
| 2026-11-13 | Question dates at least 14 days inside a validity period; "now" fixed to the corpus pin | No answers that depend on which day a change landed; results do not drift | Fewer questions near changes, where systems are most likely to fail |
| 2026-11-13 | Answer check by key tokens: all gold tokens present and no stale-only token | Objective and cheap; detects stale answers directly | Fragile for short values (`true`, `0`); flagged for review |
| 2026-11-13 | Dev/test split 70/30 grouped by fact (hash of fact key) | A fact never appears in both splits | Split sizes vary slightly from 70/30 |
| 2026-11-14 | Local fallback database without Docker: `pgserver` binaries run by `scripts/local_db.py` on localhost:5433 | Docker Desktop on the dev machine crashed on every start (its Unix-socket files became unreadable, most likely antivirus interference); same address means .env does not change | pgvector 0.6 instead of 0.8 (no iterative scan; recall was 1.00 without it at this corpus size); no btree_gist |
| 2026-11-14 | Overlap rule rewritten as `EXCLUDE USING gist (int8range(lineage_id, lineage_id, '[]') WITH &&, valid WITH &&)`; migration 0001 edited, 0004 converts older databases | Same rule without the btree_gist extension, so the schema works on Postgres builds that lack it | Editing an applied migration; acceptable because 0004 converts every existing database and fresh ones get the same result |
| 2026-11-14 | Set `hnsw.iterative_scan` only on pgvector >= 0.8 | Older pgvector rejects the setting | "iterative" mode equals "index" mode on old pgvector |
| 2026-11-15 | Entailment threshold 0.027 for nli-deberta-v3-xsmall (plan O5) | Best balanced accuracy on the calib split; matches a Gemini judge (0.93 vs 0.94) while local, free and deterministic; the small model was worse | Calibrated on one corpus and synthetic negatives; re-check on the test split and on any new corpus |
| 2026-11-13 | A path freed by a deleted file is archived (`#deleted@sha`) when another file is renamed onto it | Keeps history while respecting the unique path constraint | Archived paths look odd in `documents` |
