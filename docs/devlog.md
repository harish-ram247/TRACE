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

## Week 4

- LLM provider decision (plan O3): a free-tier hosted API, reached through any OpenAI-compatible
  `/chat/completions` endpoint. Provider and model are configuration (`LLM_BASE_URL`, `LLM_MODEL`,
  `LLM_API_KEY`). Ollama was ruled out as the main option: no discrete GPU, so a full evaluation run
  would take hours, and small local models are weak at JSON claim extraction.
- `app/core/llm.py`: client with request spacing (requests per minute), retries with backoff on 429/5xx
  (honours Retry-After), JSON mode, disk response cache (`data/llm_cache`), and a fake for tests.
- `python -m app.core.llm_check` sends two tiny live requests to verify a configured provider.
- Fixed a test that compared approximate and exact vector search across the whole dev database; it now
  only looks at its own fixture repository.
- Temporal parser (`app/temporal/parser.py`): rules for explicit dates, months, quarters, years,
  relative phrases, Vite versions and "current" words, plus change questions ("between X and Y");
  optional LLM fallback only for vague phrases ("previously", "used to"). 60+ labelled phrases in
  `tests/unit/test_temporal.py`. They show the rules are consistent; real accuracy is measured later on
  the evaluation questions.
- Vite release dates come from the corpus's git tags (`scripts/export_releases.py` ->
  `app/temporal/vite_releases.json`, committed so the API needs no clone).
- Finding: "before Vite 3" first resolved to the v3 release date (2022-07-13), but the docs on main already
  described v3 during its alpha (Node 14.18 requirement landed 2022-06-19; first v3 prerelease 2022-05-13).
  The answer cited v3 docs for a "before v3" question. Fixed: "before Vite N" now means before N's first
  prerelease.
- Answer generation (`app/generation/answer.py`): sources as `<source label="S1" ...>` blocks, citations
  mapped back to chunk ids, unknown labels flagged, `NOT_FOUND` when unanswerable, no LLM call when nothing
  is retrieved. Temporal prompt states the as-of date and source validity; plain baseline prompt has no
  dates.
- Second finding: with the right source at rank 1, Gemini still answered `NOT_FOUND` to "before Vite 3",
  apparently because no source mentions Vite 3. Prompt `answer-v2` says the time phrase has been resolved to
  the date and the sources need not mention it. After that the answer was correct (">=14.6.0").
- Pipeline (`app/pipeline.py`) and `POST /ask` (time info, answer, citations, sources with validity, model,
  prompt version, cache flag, per-stage timings). Sync endpoint on a psycopg connection pool.
- Live check on Gemini (5 questions): temporal variant correct on all three dated/current questions; the
  plain baseline answered `NOT_FOUND` to both dated questions. Five questions prove nothing statistically;
  this is a smoke test.

## Week 5

- Fact mining (`app/evaluation/facts.py`): 80 facts from documented config defaults and the Node.js
  requirement; 19 with a real value change once cosmetic edits (link targets, "4kb" vs "4 KiB", quote
  style) are ignored. Values that token matching cannot check reliably (regexes, functions, globs,
  objects) are excluded.
- Question generation (`app/evaluation/questions.py`, `scripts/build_questions.py`): 131 candidates
  (60 point-in-time, 30 current, 30 unanswerable, 11 change), split 86 dev / 45 test by fact so the
  same fact never appears in both. Gold answers come from the documentation text, never an LLM.
- Automatic checks on every candidate: the parser resolves all 131 questions to the generator's as-of
  (0 disagreements); all 30 unanswerable questions verified absent from every document valid then; every
  gold value found in its source. One bug found and fixed on the way: Node values stored without spaces
  produced a bogus "or20" token.
- Caveat: questions come from templates, so the parser sees phrasings it was written for. The
  parser-agreement number is a consistency check, not a parser accuracy result.
- First review pass (assistant, row by row against the evidence) found four generator bugs, fixed in
  code with regression tests: (1) "es2020" produced a stale token "2020"; (2) heading badges such as
  `<NonInheritBadge />` leaked into questions and made the "verified absent" check search for the wrong
  string; (3) Node versions written "18+. 20+." were cut to "18+"; (4) stale tokens included words from
  the gold default text itself ("lightningcss, but false if build.minify is disabled"). Regenerated set:
  129 candidates (60 point-in-time, 30 current, 30 unanswerable, 9 change; 81 dev / 48 test).
- The review sheet now carries the assistant's `suggested` decision and `why` (117 accept, 12 reject:
  build.ssr's undefined -> false wording change, values with no or generic tokens such as `[]`, `/`,
  `build`, `assets`). The `decision` column is left for the human reviewer; `finalize_questions
  --use-suggestions` records rows decided from a confirmed suggestion as `suggestion_confirmed`, so the
  write-up can report how many decisions were the human's own.
- Review finalised (2026-11-13), `eval/datasets/questions_v1.jsonl` frozen: 129 candidates, 12 rejected
  (9%), 117 kept: 54 point-in-time, 25 current, 30 unanswerable, 8 change; 78 dev / 39 test; 48 facts.
- How decisions were made, stated plainly for the write-up: the human reviewer decided 13 rows
  individually (agreed with all 12 suggested rejects, and accepted one row after checking it). The other
  116 rows were accepted from the assistant's suggestions without an individual human check
  (`review_source = suggestion_confirmed`). The reviewer typed the 13 decisions in the `note` column; they
  were moved to `decision` before finalising.
- Post-freeze validation: ids unique, every answerable question has gold tokens, and every gold value was
  re-found in the database text valid at its as-of date (0 failures).
- Consequence for scoring: answers to the 30 short-value questions (true/false/0) get a manual check, as
  noted in the review; any other doubt found while scoring goes into a v2, not into v1.

## Week 6

- Evaluation harness (`app/evaluation/harness.py`): runs variants per question, saves every raw output
  with provenance (git commit, dataset hash, model, prompt version), resumable after a quota stop, and
  refuses to continue a run if the dataset changed. Metrics (`app/evaluation/metrics.py`) are computed
  only from saved files: accuracy by type, stale-answer rate, abstention recall/precision, false
  abstention, retrieval recall, wrong version at rank 1, cited-gold rate, parse agreement, latency, 95%
  bootstrap CIs and a paired bootstrap for temporal minus plain; failures are classified with the
  taxonomy and written to failures.csv; short-value answers get a manual-check sheet.
- Docker Desktop stopped working on the dev machine: every start crashed because its Unix-socket files
  (`Docker/run/dockerInference`, then `docker-secrets-engine/engine.sock` under `%LOCALAPPDATA%`)
  became unreadable
  ("The file cannot be accessed by the system"), even freshly created ones. Most likely antivirus
  interference. Windows had not actually rebooted (last boot unchanged), so a restart was not tested.
- Workaround: `scripts/local_db.py` runs the PostgreSQL 16 + pgvector binaries from the `pgserver`
  package on localhost:5433. Two portability fixes came out of it: the overlap constraint no longer needs
  btree_gist (migrations 0001/0004), and `hnsw.iterative_scan` is only set on pgvector >= 0.8. Two
  Windows gotchas: `pg_ctl start` must not have captured pipes (the server inherits them and the call
  never returns), and the server must listen on `localhost` (IPv4 and IPv6) or every connection to
  "localhost" first waits 5 s on IPv6.
- The corpus was re-ingested and re-embedded into the new database from the same pinned commit.
- First evaluation run `dev-v1-plain-temporal` (78 dev questions, 156 answers, no quota stop): TRACE
  temporal accuracy 0.67 vs plain 0.38, paired difference +0.28 [+0.18, +0.38]. Details and caveats in
  `docs/results.md`.
- Main finding: date-phrased questions work (0.86), version-phrased ones do not (0.11, 83% NOT_FOUND) even
  though the parser resolves them correctly. The model refuses when sources do not mention the version named
  in the question. Next step: do not show the raw time phrase to the generator.
- Prompt `answer-v3` (remove the resolved time phrase, state the date): run `dev-v1-answer-v3` raised TRACE
  dev accuracy from 0.67 to 0.76 (paired vs plain +0.37 [+0.26, +0.49]); version-phrased questions went from
  2/18 to 10/18 correct. 3 of the 4 remaining "stale" failures are checker false negatives (correct Node.js
  answers that list dropped versions); flagged for the manual check rather than patched in the checker.
