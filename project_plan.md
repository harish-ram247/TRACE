# TRACE: Project Plan

> Project name: **TRACE** (**T**emporal **R**etrieval with **A**ttributed **C**laim **E**vidence). A time-aware, claim-verified RAG system.
> This document is the single source of truth for scope, design, modules, phases, evaluation and deployment.
> Update it as decisions change. Tick the checkboxes as work completes.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Scope](#2-scope)
3. [Glossary](#3-glossary)
4. [System architecture](#4-system-architecture)
5. [Tech stack and decisions](#5-tech-stack-and-decisions)
6. [Repository structure](#6-repository-structure)
7. [Data model](#7-data-model)
8. [Modules](#8-modules)
9. [Development phases (week by week)](#9-development-phases-week-by-week)
10. [Evaluation design](#10-evaluation-design)
11. [Testing strategy](#11-testing-strategy)
12. [Deployment plan](#12-deployment-plan)
13. [Security, privacy and licensing](#13-security-privacy-and-licensing)
14. [Risk register](#14-risk-register)
15. [Scope control and cut lines](#15-scope-control-and-cut-lines)
16. [Definition of done](#16-definition-of-done)
17. [Honest reporting and README guidance](#17-honest-reporting-and-readme-guidance)
18. [Open decisions](#18-open-decisions)
19. [Appendix](#19-appendix)

---

## 1. Project overview

### 1.1 Problem

Documents change over time. A value that was "100 requests per minute" in 2023 may be "500" in 2024. A standard RAG system stores every version of a document as plain text, retrieves whichever passages look similar to the question, and answers confidently. Two things go wrong:

1. **Time confusion.** The system mixes old and new versions, or answers from the wrong one. It cannot answer "what was the limit in June 2023?" reliably.
2. **Unproven answers.** Citations are attached to answers, but nothing checks that the cited passage actually supports the claim.

These two failures interact. An answer can be **faithful to its source and still wrong** because the source is outdated. A faithfulness check alone passes it. A time filter alone cannot catch a model that misstates the correct source.

### 1.2 Solution

TRACE is a RAG backend that:

1. Stores every version of every passage with a **validity interval** (when it was true).
2. Understands the **time intent** of a question (as-of date, "currently", "what changed").
3. Retrieves only passages **valid at the requested time**.
4. Generates an answer with citations.
5. Splits the answer into **atomic claims** and verifies each one against its cited passage using an entailment model.
6. Checks that each cited passage was **valid on the as-of date**.
7. Labels every claim as `supported_current`, `supported_outdated` or `unsupported`, then revises once, flags, or abstains.

### 1.3 Worked example

| Version | Valid from | Valid until | Text |
|---|---|---|---|
| v1 | 2023-01-10 | 2024-02-01 | "The API allows 100 requests per minute." |
| v2 | 2024-02-01 | open | "The API allows 500 requests per minute." |

- Question: "What was the rate limit in June 2023?"
- Plain RAG: may answer 500, or blend both.
- TRACE: as-of = 2023-06-01, retrieves v1, answers "100 requests per minute", cites v1, verifier confirms the claim is entailed and v1 was valid on that date.
- Question: "What is the limit today?" with a model that cites v1 by mistake: the claim is entailed but v1 is outdated, so it is labelled `supported_outdated` and the system corrects or flags it.

### 1.4 Goals

- Build a working, deployed, tested backend that implements the full pipeline.
- Produce a **rigorous evaluation** comparing four system variants with measured numbers.
- Learn: database design (range types, indexes), hybrid retrieval, evaluation methodology, NLI-based verification, async pipelines, containerised deployment.

### 1.5 Non-goals

- Not a novel research technique. The claim is a careful end-to-end implementation and evaluation of the combination.
- No user accounts, multi-tenancy, permissions or access control.
- No graph retrieval, multi-corpus support or fine-tuning (unless time remains and they are listed in stretch goals).
- No polished frontend. A minimal demo UI only.
- No high availability or production-scale performance.

### 1.6 Success criteria

| Criterion | Target |
|---|---|
| End-to-end pipeline works on the chosen corpus | Yes |
| Evaluation set size | At least 100 questions, with a manually reviewed sample |
| Four variants compared with CIs | Yes |
| Verifier accuracy reported on hand-labelled claims | At least 100 claims |
| Publicly reachable demo | Yes (or recorded video if environment is torn down) |
| README with results, limits and architecture | Yes |

Targets for improvement over baseline are **not pre-committed**. Report what is measured.

---

## 2. Scope

### 2.1 Minimum strong version (must ship)

- Git-history ingestion into versioned chunks with validity intervals.
- Hybrid (vector plus keyword) time-filtered retrieval.
- Temporal query parsing (as-of date and "current").
- Answer generation with citations.
- Claim extraction, NLI verification, validity check, labelling, abstention.
- Evaluation harness and dataset (point-in-time, current, unanswerable at minimum).
- API, tests, CI, Docker Compose, deployment.
- README, results and demo.

### 2.2 Stretch goals (only if ahead of schedule)

- "What changed between X and Y" questions with side-by-side version retrieval.
- Cross-encoder reranker.
- Incremental re-ingestion on repository updates (webhook or scheduled pull).
- LLM-as-judge comparison against the NLI verifier.
- Terraform for AWS.
- Simple dashboard of evaluation results.

### 2.3 Explicitly out of scope

Permissions, multiple corpora, fine-tuning embedding models, mobile or polished web UI, real-time collaborative editing.

---

## 3. Glossary

| Term | Meaning |
|---|---|
| RAG | Retrieval-Augmented Generation. Retrieve passages, then generate an answer from them |
| Chunk | A passage of a document, usually one section |
| Lineage | The chain of versions of the "same" passage over time |
| Validity interval | The time range during which a chunk version was true (`valid_from` to `valid_until`) |
| As-of date | The date the user's question refers to |
| Claim | One atomic factual statement extracted from an answer |
| NLI | Natural Language Inference. A model that decides if a premise entails, contradicts or is neutral to a hypothesis |
| Entailment | The premise supports the hypothesis |
| Faithful but stale | Claim supported by its cited chunk, but the chunk was not valid on the as-of date |
| RRF | Reciprocal Rank Fusion. A simple way to merge ranked lists |
| Abstain | Return "cannot answer from available evidence" instead of guessing |

---

## 4. System architecture

### 4.1 Component diagram

```
                      +-----------------------+
 Git repository ----> |  Ingestion pipeline   |
 (docs history)       |  walk commits, parse, |
                      |  chunk, hash, embed   |
                      +-----------+-----------+
                                  |
                                  v
                      +-----------------------+
                      |   PostgreSQL          |
                      |   - chunks (valid     |
                      |     tstzrange)        |
                      |   - pgvector index    |
                      |   - full-text index   |
                      |   - runs / claims /   |
                      |     verdicts          |
                      +-----------+-----------+
                                  ^
                                  |
 User ---> FastAPI ---> Temporal parser ---> Hybrid retrieval (time-filtered)
              |                                        |
              |                                        v
              |                               Answer generation (LLM)
              |                                        |
              |                                        v
              |                           Claim extraction (LLM, JSON)
              |                                        |
              |                                        v
              |                    Verification: NLI entailment + validity check
              |                                        |
              |                                        v
              +<------------- Labelled answer, citations, version dates
```

### 4.2 Request flow (query time)

1. Receive question (and optional explicit `as_of` override).
2. **Temporal parse:** extract as-of date, intent type (`point_in_time`, `current`, `change`), confidence.
3. **Retrieve:** hybrid search where `valid @> as_of`. Fuse vector and keyword results with RRF. Optional rerank.
4. **Generate:** prompt with top chunks (each tagged with ID and validity dates), request answer with chunk-ID citations.
5. **Extract claims:** LLM returns JSON list of atomic claims, each with cited chunk IDs.
6. **Verify:** for each claim, run NLI(premise = chunk text, hypothesis = claim). Check cited chunk validity against as-of date.
7. **Label and act:** apply labelling policy. Revise once if unsupported or outdated claims exist, otherwise flag or abstain.
8. **Respond and log:** return structured answer. Store run, claims and verdicts for evaluation and audit.

### 4.3 Ingestion flow

1. Clone or open the target repository.
2. Walk commits in chronological order, recording commit date.
3. For each commit, find changed documentation files (added, modified, deleted).
4. Parse changed files into sections (heading-based chunks).
5. For each section, compute a content hash and match to an existing lineage (same file path plus section path or high text similarity).
6. If content is unchanged, keep the existing chunk open. If changed, close the old chunk's validity at the commit time and insert a new chunk. If removed, close validity.
7. Compute embeddings and keyword vectors for new chunks only.

---

## 5. Tech stack and decisions

### 5.1 Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | Type hints throughout |
| API | FastAPI, Pydantic v2, Uvicorn | Async endpoints |
| Database | PostgreSQL 16 with `pgvector`, `btree_gist` | Single store for vectors, text and time |
| DB access | SQLAlchemy 2.0 (async), asyncpg | Raw SQL for retrieval queries |
| Migrations | Alembic | Every schema change is a migration |
| Git access | GitPython or pygit2 | Walk history programmatically |
| Parsing | markdown-it-py (or the corpus's native format) | Heading-based sections |
| Embeddings | Small sentence-transformers model (384-dim class, e.g. bge-small or MiniLM family) | Local, CPU. Final choice in Open Decisions |
| Keyword search | PostgreSQL full-text (`tsvector`, GIN) | Ranked with `ts_rank` |
| Fusion | Reciprocal Rank Fusion (k = 60 as starting value) | Implemented in Python or SQL |
| Reranker (stretch) | Small cross-encoder | Optional |
| Temporal parsing | `dateparser` plus rules, LLM JSON fallback | Return confidence |
| LLM | Free-tier hosted API or local Ollama behind an interface | Generation and claim extraction |
| Verifier | Pretrained NLI cross-encoder from Hugging Face | Compare to LLM judge (stretch) |
| Job queue | Postgres job table with `FOR UPDATE SKIP LOCKED` | Avoids extra service |
| Evaluation | pytest, custom harness, pandas, matplotlib | Results saved as CSV/JSON |
| Demo UI | Streamlit with a date slider | Minimal |
| Lint/format/types | ruff, black (or ruff format), mypy (optional) | In CI |
| Containers | Docker, Docker Compose | Local and server |
| CI/CD | GitHub Actions | Tests, lint, build, deploy |
| Hosting | AWS EC2 (small), Caddy for HTTPS | Within free tier or credits |
| IaC (stretch) | Terraform | Optional |

### 5.2 Key design decisions

| # | Decision | Reason | Trade-off |
|---|---|---|---|
| D1 | One PostgreSQL for everything | Fewer moving parts, transactional consistency, range types for time | Vector search at scale is slower than a dedicated engine. Fine for a student-size corpus |
| D2 | Validity as `tstzrange` with GiST index | `valid @> as_of` is a native, indexed operation. Exclusion constraint prevents overlapping versions | Requires `btree_gist` |
| D3 | Chunk by heading section | Natural units, stable across edits | Very long sections need splitting |
| D4 | Lineage IDs link versions | Enables "what changed" and supersession checks | Lineage matching can err (see risks) |
| D5 | NLI model as primary verifier | Cheap, fast, measurable | Imperfect. Must calibrate and report accuracy |
| D6 | LLM behind an interface | Swap providers, avoid lock-in, free-tier friendly | Slight abstraction cost |
| D7 | Postgres-based queue | No Redis needed | Lower throughput. Acceptable |
| D8 | Models run on CPU | No GPU cost | Slower. Keep models small and cache |

Record any change to these in `docs/decisions.md`.

---

## 6. Repository structure

```
trace/
  app/
    api/            # FastAPI routers, schemas
    core/           # config, logging, db session, LLM interface
    ingest/         # git walker, parser, chunker, lineage matcher
    retrieval/      # embeddings, hybrid search, fusion, rerank
    temporal/       # query time parsing
    generation/     # prompts, answer generation
    verification/   # claim extraction, NLI, labelling policy
    jobs/           # background worker
  eval/
    datasets/       # questions.jsonl, claim_labels.jsonl
    runs/           # saved run outputs
    reports/        # tables, charts
    harness.py      # runs variants, computes metrics
  migrations/       # Alembic
  tests/
    unit/
    integration/
    fixtures/       # tiny synthetic versioned corpus
  ui/               # Streamlit demo
  docker/           # Dockerfile(s), compose files, Caddyfile
  infra/            # Terraform (stretch)
  scripts/          # one-off tools (build question set, label helpers)
  docs/             # decisions.md, architecture.md, results.md
  .github/workflows/
  .env.example
  README.md
  project_plan.md
```

---

## 7. Data model

### 7.1 Tables

| Table | Key columns |
|---|---|
| `documents` | `id`, `source_path`, `repo_url`, `created_at` |
| `chunks` | `id`, `lineage_id`, `document_id`, `section_path`, `text`, `content_hash`, `embedding`, `tsv`, `valid` (tstzrange), `introduced_commit`, `removed_commit`, `supersedes_id` |
| `ingest_runs` | `id`, `repo_ref`, `started_at`, `finished_at`, `status`, `commits_processed` |
| `jobs` | `id`, `type`, `payload`, `status`, `attempts`, `locked_at`, `error` |
| `queries` | `id`, `question`, `as_of`, `intent`, `parse_confidence`, `variant`, `created_at` |
| `answers` | `id`, `query_id`, `answer_text`, `model`, `latency_ms`, `tokens_in`, `tokens_out` |
| `claims` | `id`, `answer_id`, `claim_text`, `cited_chunk_ids` |
| `verdicts` | `id`, `claim_id`, `nli_label`, `nli_score`, `chunk_valid_at_as_of`, `final_label` |

### 7.2 Core SQL (reference)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE chunks (
  id               BIGSERIAL PRIMARY KEY,
  lineage_id       BIGINT NOT NULL,
  document_id      BIGINT NOT NULL REFERENCES documents(id),
  section_path     TEXT NOT NULL,
  text             TEXT NOT NULL,
  content_hash     TEXT NOT NULL,
  embedding        vector(384),            -- dimension depends on chosen model
  tsv              tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  valid            tstzrange NOT NULL,     -- upper bound NULL means still valid
  introduced_commit TEXT,
  removed_commit    TEXT,
  supersedes_id    BIGINT REFERENCES chunks(id),
  EXCLUDE USING gist (lineage_id WITH =, valid WITH &&)
);

CREATE INDEX chunks_valid_gist ON chunks USING gist (valid);
CREATE INDEX chunks_tsv_gin    ON chunks USING gin  (tsv);
CREATE INDEX chunks_emb_hnsw   ON chunks USING hnsw (embedding vector_cosine_ops);
```

Time-filtered retrieval (sketch):

```sql
-- keyword branch
SELECT id, ts_rank(tsv, plainto_tsquery('english', :q)) AS score
FROM chunks
WHERE valid @> :as_of::timestamptz
  AND tsv @@ plainto_tsquery('english', :q)
ORDER BY score DESC LIMIT 20;

-- vector branch
SELECT id, 1 - (embedding <=> :q_emb) AS score
FROM chunks
WHERE valid @> :as_of::timestamptz
ORDER BY embedding <=> :q_emb LIMIT 20;
```

**Known issue to test:** approximate vector indexes combined with restrictive filters can return fewer results than requested. Measure this and, if needed, increase the search breadth, use iterative scanning options in current pgvector versions, or pre-filter by time range before ranking.

### 7.3 Invariants (must be enforced by tests)

- No two versions in the same lineage have overlapping validity.
- Every chunk has a non-empty `text`, a valid `content_hash` and an embedding.
- A superseded chunk's `valid` upper bound equals its successor's lower bound.
- Re-running ingestion on the same history is idempotent (no duplicate chunks).

---

## 8. Modules

Each module lists purpose, tasks, deliverables, acceptance criteria and tests.

### M1. Foundation and infrastructure

**Purpose:** reproducible local environment and project skeleton.

- [ ] Create repository, license, `.gitignore`, `README` stub.
- [ ] Docker Compose with Postgres (pgvector) and the API service.
- [ ] Config via environment variables (`.env.example`, no secrets committed).
- [ ] Structured logging, health endpoint.
- [ ] Alembic set up, first migration (extensions, `documents`, `chunks`).
- [ ] CI: ruff, pytest on every push.

**Acceptance:** `docker compose up` starts everything. `/health` returns OK. CI is green. Migration applies cleanly on an empty database and rolls back.

### M2. Corpus selection and git ingestion

**Purpose:** turn a repository's history into ordered change events.

- [ ] Choose corpus using the criteria in section 18 and **verify its license**.
- [ ] Document the corpus in `docs/corpus.md` (source, license, commit range, size, why chosen).
- [ ] Implement a commit walker producing `(commit, date, changed_files, change_type)`.
- [ ] Handle renames, deletions and merge commits (document the policy: e.g. first-parent history).
- [ ] Limit the commit range to keep size manageable (decide and record).

**Acceptance:** a script prints a clean chronological change log for the chosen range. Tests use a small synthetic repository created in a fixture.

### M3. Parsing, chunking and versioned storage

**Purpose:** build versioned chunks with correct validity intervals.

- [ ] Parse files into heading-based sections with a stable `section_path`.
- [ ] Split oversized sections (token limit, overlap policy recorded).
- [ ] Compute content hash (normalise whitespace before hashing).
- [ ] Lineage matching: same `(document, section_path)` first. Fall back to text similarity above a recorded threshold for moved or renamed sections.
- [ ] Open, close and supersede chunk versions per the rules in 4.3.
- [ ] Idempotent ingestion (safe to re-run).
- [ ] Ingestion runs recorded in `ingest_runs`.

**Acceptance:** invariants in 7.3 hold on the full corpus. Spot-check at least 20 lineages by hand against `git log`. Unit tests cover add, modify, delete, rename, unchanged and re-run cases.

### M4. Embeddings and hybrid retrieval

**Purpose:** fast, correct, time-filtered search.

- [ ] Embedding service (batching, caching, model name stored in config).
- [ ] Vector and keyword retrieval with the time filter.
- [ ] RRF fusion; make `k`, top-N per branch and final top-K configurable.
- [ ] Verify the filtered-vector-search issue from 7.2 and document findings.
- [ ] Retrieval API function returning chunks with ID, text, validity dates and scores.

**Acceptance:** for a hand-made set of 20 queries with known gold chunks, report recall@5 and recall@10 at several as-of dates. No result ever has `valid` excluding the as-of date (test).

### M5. Temporal query understanding

**Purpose:** convert natural language time intent into structured parameters.

- [ ] Intent classes: `point_in_time`, `current`, `change` (stretch), `unspecified`.
- [ ] Rule-based and `dateparser` extraction first. LLM JSON fallback second.
- [ ] Output: `as_of`, `intent`, `confidence`, and the matched phrase.
- [ ] Policy for `unspecified`: default to current time, and mention the assumed date in the response.
- [ ] Policy for ambiguous or future dates: ask for clarification or default and flag.
- [ ] Accept an explicit `as_of` API parameter that overrides parsing.

**Acceptance:** at least 60 labelled test phrases (varied formats: "in June 2023", "before the 2.0 release", "last year", "as of 2024-03-01", "now"). Report parser accuracy. Failures are logged.

### M6. Answer generation

**Purpose:** produce cited answers from retrieved chunks.

- [ ] LLM interface (provider-agnostic, retries, timeouts, token accounting).
- [ ] Prompt that includes chunk IDs and validity dates, instructs citation by ID, and instructs to say "not found" if evidence is absent.
- [ ] Treat chunk text as untrusted data (delimiters, no instruction following from documents).
- [ ] Parse citations out of the answer. Reject citations to chunks not provided.
- [ ] Baseline variant: same pipeline with **no time filter** (used for comparison).

**Acceptance:** every answer has parseable citations or an explicit "not found". Prompt versions are recorded with each run.

### M7. Claim extraction and verification

**Purpose:** check each claim against its source and its validity.

- [ ] Claim extraction: LLM returns JSON of atomic claims with cited chunk IDs. Validate against a schema, retry on malformed output.
- [ ] NLI check: premise = cited chunk text (or the best-matching sentences), hypothesis = claim. Handle long premises (sentence windowing).
- [ ] Validity check: `chunk.valid @> as_of`. Also detect "superseded before today" for `current` intent.
- [ ] Record NLI label, score, validity flag and final label per claim.
- [ ] Calibrate the entailment threshold on hand-labelled claims (see section 10.4).

**Acceptance:** verifier precision/recall on the labelled sample is reported. A confusion matrix is saved. Known failure modes (negation, numbers, long premises) are listed in `docs/verifier_notes.md`.

### M8. Labelling policy and abstention

**Purpose:** decide what to do with each verdict.

| Claim state | Action |
|---|---|
| `supported_current` | Keep |
| `supported_outdated` | Attempt one revision with the correct version. If none exists, flag or drop |
| `unsupported` | Attempt one revision. If still unsupported, drop the claim |
| All claims dropped or no valid chunks retrieved | Abstain with a clear message |

- [ ] Implement the policy as a pure, unit-tested function.
- [ ] Limit revision to one retry to bound cost and latency.
- [ ] Response includes per-claim labels, cited versions and their validity dates.

**Acceptance:** policy tests cover each row of the table. Abstention triggers correctly on the "not yet existing" question type.

### M9. Evaluation harness and dataset

**Purpose:** produce trustworthy numbers. See section 10 for full design.

- [ ] Question generation script from git diffs.
- [ ] Manual review workflow and recorded reviewer decisions.
- [ ] Harness that runs the four variants and stores raw outputs.
- [ ] Metric computation with bootstrap confidence intervals.
- [ ] Hand-labelled claim set for verifier calibration.
- [ ] Report generator (tables and charts).

**Acceptance:** one command reproduces all tables from saved raw outputs. Dataset and labels are versioned in the repository.

### M10. API and backend hardening

**Purpose:** a clean, tested, observable service.

- [ ] Endpoints: `POST /ask`, `GET /chunks/{id}`, `GET /lineages/{id}`, `POST /ingest` (admin or script only), `GET /health`.
- [ ] Request validation, error model, timeouts, size limits.
- [ ] Rate limiting (simple, in-process or database-backed).
- [ ] Per-stage latency and token logging.
- [ ] Background worker for ingestion jobs with retries and failure recording.
- [ ] Integration tests against a real Postgres container.

**Acceptance:** OpenAPI docs are accurate. Integration tests pass in CI. Killing the worker mid-job leaves no corrupt state (job is retried safely).

### M11. Demo UI

**Purpose:** show the behaviour visually.

- [ ] Streamlit page: question box, **date slider**, answer panel with claim badges (current / outdated / unsupported), source panel with version dates.
- [ ] Side-by-side view: baseline answer versus TRACE answer.
- [ ] A few preset demo questions that clearly show the difference.

**Acceptance:** moving the slider changes the answer for a prepared question. UI works against the deployed API.

### M12. Deployment and CI/CD

See section 12.

- [ ] Production Dockerfile, health checks.
- [ ] Compose file for the server.
- [ ] CI builds the image and runs tests.
- [ ] Deploy workflow (manual trigger is acceptable).
- [ ] Budget alarm and teardown instructions.

**Acceptance:** public URL serves the API and UI over HTTPS. Teardown and redeploy documented and tested once.

### M13. Documentation and release

- [ ] README with problem, example, architecture diagram, results table, limits.
- [ ] `docs/architecture.md`, `docs/decisions.md`, `docs/results.md`, `docs/corpus.md`, `docs/verifier_notes.md`.
- [ ] Demo video (2 to 3 minutes).
- [ ] Tag a release.

**Acceptance:** a stranger can clone, run `docker compose up`, load the sample data and reproduce the main table by following the README.

---

## 9. Development phases (week by week)

Assumes about 10 to 15 hours per week. Total about 11 weeks. Exit criteria must be met before moving on, or the slip must be recorded.

### Phase 0. Preparation (before Week 1, 2 to 3 days)

- [ ] Read this plan fully. Resolve the "Open decisions" that block Week 1 (corpus candidates, LLM provider).
- [ ] Set up accounts and local tools (Docker, Python, Git).
- [ ] Skim the pgvector and Postgres range-type documentation.

### Phase 1. Foundation (Weeks 1 to 2)

**Week 1: environment and corpus**
- [ ] M1 complete (Compose, config, migrations, CI).
- [ ] Shortlist 2 to 3 corpus candidates. Check license, commit history size, frequency of factual changes. Pick one and write `docs/corpus.md`.
- [ ] Write the failure taxonomy (Appendix A) into `docs/`.
- Exit: environment reproducible, corpus chosen and documented.

**Week 2: ingestion**
- [ ] M2 complete (commit walker).
- [ ] M3 started: parser, chunker, lineage logic, validity handling.
- [ ] Fixture repository and unit tests for add/modify/delete/rename/rerun.
- Exit: invariants (7.3) pass on the fixture.

### Phase 2. Retrieval core (Weeks 3 to 4)

**Week 3: versioned store and search**
- [ ] M3 finished on the full corpus, 20 lineages spot-checked.
- [ ] M4: embeddings, hybrid retrieval, time filter, RRF.
- [ ] Start drafting evaluation questions in parallel (about 30 minutes per day).
- Exit: retrieval works at any as-of date. Recall measured on the 20-query hand set.

**Week 4: generation and temporal parsing**
- [ ] M5 temporal parser with labelled phrase tests.
- [ ] M6 answer generation, citations, baseline (no-time) variant.
- [ ] Basic `POST /ask`.
- Exit: end-to-end baseline and temporal answers work on sample questions.

### Phase 3. Evaluation foundation (Weeks 5 to 6)

**Week 5: dataset**
- [ ] Question generation from diffs (script).
- [ ] Manual review: target at least 100 final questions across types.
- [ ] Freeze dataset v1 (do not change it after seeing results, except to fix errors, and log fixes).

**Week 6: baseline results**
- [ ] M9 harness: run plain RAG and temporal-retrieval variants.
- [ ] Compute accuracy, stale-answer rate, retrieval recall.
- [ ] Error analysis: read at least 30 failures and categorise them.
- Exit: first comparison table (baseline versus temporal retrieval) with CIs.

### Phase 4. Verification (Weeks 7 to 8)

**Week 7: verifier pipeline**
- [ ] M7: claim extraction, NLI, validity check.
- [ ] M8: labelling policy, revision, abstention.
- Exit: every answer returns claim-level verdicts.

**Week 8: calibration and ablations**
- [ ] Hand-label at least 100 claims (include tricky cases: numbers, negation, partial support).
- [ ] Calibrate the threshold. Report precision, recall, F1 and confusion matrix.
- [ ] Run all four variants. Compute faithful-but-stale rate and unsupported-claim rate.
- [ ] Full error analysis and `docs/verifier_notes.md`.
- Exit: full results table with CIs and the verifier's own accuracy.

### Phase 5. Backend hardening and delivery (Weeks 9 to 11)

**Week 9: hardening**
- [ ] M10: endpoints, validation, worker, rate limit, integration tests.
- [ ] CI includes integration tests and a small evaluation smoke test on the fixture.
- Exit: CI green, OpenAPI docs correct.

**Week 10: deployment and UI**
- [ ] M11 Streamlit demo with date slider.
- [ ] M12 deploy to AWS. HTTPS, budget alarm, teardown tested.
- Exit: public URL works.

**Week 11: release**
- [ ] M13 documentation, diagram, results write-up, video.
- [ ] Buffer for slipped work.
- Exit: Definition of Done (section 16) satisfied.

### Weekly routine

- Start of week: pick that week's tasks from this file.
- End of week: tick completed items, write 3 to 5 lines in `docs/devlog.md` (what worked, what broke, what changed).
- Any decision that changes scope goes into `docs/decisions.md`.

---

## 10. Evaluation design

### 10.1 Variants compared

| Variant | Description |
|---|---|
| V0 Plain RAG | Hybrid retrieval over all versions with no time filter. Generation with citations |
| V1 Temporal | V0 plus time parsing and time-filtered retrieval |
| V2 Verified | V0 plus claim extraction and verification (no time filter) |
| V3 Full | V1 plus verification, validity check and abstention |

Same corpus, same embedding model, same LLM, same prompts apart from the changes each variant requires. Fix random seeds and record model versions.

### 10.2 Question types

| Type | Example | Expected behaviour |
|---|---|---|
| Point-in-time | "As of June 2023, what is the rate limit?" | Answer from the version valid then |
| Current | "What is the rate limit now?" | Answer from the latest version |
| Unanswerable-at-date | "As of 2022, what is the rate limit?" (feature added in 2023) | Abstain |
| Change (stretch) | "What changed in the rate limit between 2023 and 2024?" | Both values, correct order |

Target mix (adjust to what the corpus supports): about 40% point-in-time, 25% current, 20% unanswerable, 15% change.

### 10.3 Dataset construction

1. From the git history, find facts that changed (a number, a default, a version, a name).
2. Generate candidate questions and gold answers for several dates using a script and LLM assistance, with the gold answer **taken from the actual file content at that commit**, not from the LLM.
3. Manually review a sample (target: all of them if feasible, otherwise at least 30 percent). Record reviewer decisions and the rejection rate.
4. Store as `eval/datasets/questions.jsonl`.

Record format:

```json
{
  "id": "q_0042",
  "question": "As of June 2023, what is the API rate limit?",
  "as_of": "2023-06-01T00:00:00Z",
  "type": "point_in_time",
  "gold_answer": "100 requests per minute",
  "gold_chunk_versions": [1234],
  "stale_distractors": ["500 requests per minute"],
  "answerable": true,
  "reviewed": true
}
```

`stale_distractors` are values from versions not valid at the as-of date. They make stale-answer detection objective.

### 10.4 Verifier calibration set

- Sample claims from system outputs across all variants.
- Hand-label each: `entailed`, `not_entailed`, with a note for tricky cases.
- Include at least 100 claims, and make sure numeric claims, negations and partially supported claims are represented.
- Split into calibration and held-out halves. Tune the threshold on the first half, report on the second.

### 10.5 Metrics

| Metric | Definition |
|---|---|
| Answer accuracy | Answer contains the gold value and none of the stale distractors for the as-of date (rule-based), checked by manual review on a sample |
| Stale-answer rate | Fraction of answerable questions whose answer contains a stale distractor value |
| Unsupported-claim rate | Fraction of claims not entailed by their cited chunk (by verifier, validated on the labelled set) |
| Faithful-but-stale rate | Fraction of claims entailed by the cited chunk where the chunk was not valid at the as-of date |
| Abstention precision / recall | On the unanswerable and answerable subsets |
| Retrieval recall@K | Gold chunk version appears in the top K |
| Latency | p50 and p95 end-to-end and per stage |
| Cost | Tokens per question (and money if using a paid API) |

### 10.6 Statistical practice

- Report sample sizes next to every number.
- Use bootstrap confidence intervals. With about 100 questions, differences of a few points are noise. Say so.
- Do not tune prompts or thresholds on the whole dataset and then report on it. Keep a held-out split (for example 70/30), and decide beforehand.
- Keep raw outputs so every number can be recomputed.

### 10.7 Error analysis

For each variant, read at least 30 failures and categorise: retrieval miss, wrong version, temporal parse error, claim extraction error, verifier error, generation error. Report the breakdown. This often matters more than the headline number.

---

## 11. Testing strategy

| Level | Scope | Tools |
|---|---|---|
| Unit | Chunker, hash, lineage matcher, temporal parser, RRF, labelling policy | pytest |
| Property-style | Random version histories: invariants (7.3) always hold; ingestion idempotent | pytest, hypothesis |
| Integration | Ingestion into a real Postgres, retrieval at multiple dates, API endpoints | pytest, Docker |
| Evaluation smoke | Tiny fixture dataset through the full pipeline, deterministic stubs for LLM | pytest in CI |
| Manual | Spot checks of lineages and answers | Checklists in `docs/` |

Rules:
- LLM calls are stubbed in unit and CI tests. Real-model tests are separate and not run in CI.
- Every bug found gets a regression test.
- Every invariant in 7.3 has at least one test.

CI pipeline: lint, type check (optional), unit tests, integration tests with Postgres service, Docker build.

---

## 12. Deployment plan

### 12.1 Approach

Local-first. Build and test everything with Docker Compose. Deploy to AWS only once the system works end to end (around Week 10), so free-tier or credit limits do not run out while coding.

### 12.2 Target architecture

- One small **EC2** instance running Docker Compose: API, worker, Postgres with pgvector, Streamlit, Caddy.
- **Caddy** for automatic HTTPS (needs a domain or free dynamic-DNS hostname).
- Security group exposing only 80 and 443. SSH restricted to your IP, or use SSM Session Manager.
- Secrets via environment file on the server or SSM Parameter Store (standard parameters). No secrets in the repository.
- Optional: S3 for backups or dataset storage.

### 12.3 Constraints and cautions

- **Memory:** embedding and NLI models need RAM. A very small instance may not fit Postgres, the API and both models. Options: precompute all embeddings during ingestion on your laptop and load them, use small models, add swap, or allow the verifier to call a hosted inference API. Check which instance types your AWS plan allows.
- **Cost control:** set a budget alarm on day one. Avoid load balancers, NAT gateways, managed databases and other always-on paid services. Check current free-tier or credit terms for your account, as they have changed over time.
- **Teardown:** document how to stop and destroy everything, and test it once. Keep a recorded demo and screenshots so the project is showable afterward.

### 12.4 CI/CD

- On every push: lint, tests, image build.
- On tag or manual trigger: build image, push to a registry (GitHub Container Registry is free), SSH or SSM to the server, pull and restart.
- Prefer OIDC to AWS over long-lived access keys if you automate AWS actions.

### 12.5 Deployment checklist

- [ ] `docker compose -f docker/compose.prod.yml up` works locally.
- [ ] HTTPS valid, HTTP redirects to HTTPS.
- [ ] Health endpoint monitored.
- [ ] Database volume backed up (a simple `pg_dump` script is enough).
- [ ] Budget alarm active.
- [ ] Teardown tested.

---

## 13. Security, privacy and licensing

- **Documents are untrusted input.** A document could contain text that instructs the model. Keep chunk text inside clear delimiters, never let it alter system instructions, and never give the model tools that can act.
- **Input validation:** length limits on questions, validated dates, strict JSON schemas for LLM output.
- **Secrets:** environment variables or a secret store. Never commit keys. Rotate if leaked.
- **Rate limiting** on public endpoints to protect free-tier LLM quotas.
- **Ingestion endpoint** is not public. Run ingestion by script or authenticated admin call.
- **Licensing:** confirm the corpus license permits copying, modifying and displaying the text. Record the license and attribution in `docs/corpus.md` and the README. If unsure, pick a different corpus.
- **Personal data:** do not ingest anything containing personal data. Do not log full user questions beyond what the evaluation needs.
- **Dependencies:** pin versions, enable dependency scanning in CI if available.

---

## 14. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Evaluation set is too small or noisy to show differences | Medium | High | Start in Week 3, review manually, report confidence intervals honestly |
| R2 | NLI verifier is inaccurate on numbers and negation | High | High | Calibrate on labelled data, report its accuracy, list failure modes, consider LLM-judge comparison |
| R3 | Lineage matching mislinks sections after refactors | Medium | Medium | Prefer path-based matching, similarity threshold with manual spot checks, log uncertain matches |
| R4 | Corpus has too few factual changes | Medium | High | Evaluate candidates before committing (count changed facts). Switch early if poor |
| R5 | Filtered vector search returns too few results | Medium | Medium | Test in Week 3, use wider search or pre-filtering, document finding |
| R6 | Free-tier LLM limits slow experiments | Medium | Medium | Cache LLM outputs, use a small local model for development, batch runs |
| R7 | Models do not fit on the cheap server | Medium | Medium | Small models, precomputed embeddings, hosted inference fallback |
| R8 | Scope creep | High | High | Section 15 cut lines, weekly review of this plan |
| R9 | Temporal parsing ambiguity (relative dates, release names) | Medium | Medium | Return confidence, default policy, flag assumed date in response |
| R10 | Schedule slip from exams or placements | High | Medium | 11-week plan includes buffer, cut lines are pre-agreed |
| R11 | License problem with corpus | Low | High | Check before starting, record in `docs/corpus.md` |
| R12 | Results show no improvement | Medium | Medium | Still a valid result. Report honestly with error analysis. The engineering and evaluation remain valuable |

---

## 15. Scope control and cut lines

**Drop first, in this order, if behind schedule:**
1. Terraform and deploy automation (deploy manually and document it).
2. Reranker.
3. "What changed" question type.
4. LLM-judge comparison.
5. Demo UI polish (keep the date slider).
6. Rate limiting.

**Never drop:**
- Validity model with invariants and tests.
- Time-filtered hybrid retrieval.
- Claim verification with a calibrated threshold and reported accuracy.
- The four-variant evaluation with error analysis.
- A working deployment or recorded demo.
- README with honest results and limitations.

**Scope rules:**
- No new feature unless it is in this file. Add it here first with a reason, and remove something of equal size.
- One corpus only.
- Freeze the question set before running final experiments.

---

## 16. Definition of done

- [ ] All "must ship" items in section 2.1 are complete.
- [ ] Invariants in 7.3 are enforced by passing tests.
- [ ] CI is green on the main branch.
- [ ] Evaluation dataset (at least 100 questions) and claim labels (at least 100) are in the repository.
- [ ] One command regenerates all result tables from saved outputs.
- [ ] Results table includes confidence intervals, sample sizes and the verifier's own accuracy.
- [ ] Error analysis written up.
- [ ] Public demo or recorded demo exists.
- [ ] README includes: problem, worked example, architecture diagram, results, limitations, how to run, corpus license and attributions.
- [ ] `docs/decisions.md` and `docs/devlog.md` are up to date.
- [ ] You can explain every design decision and every number without notes.

---

## 17. Honest reporting and README guidance

- Only claim numbers you measured. Include sample size and uncertainty.
- Describe the contribution accurately: "an end-to-end implementation and evaluation combining temporal retrieval with claim-level verification", not "a new technique".
- Include a **Related work** section naming prior work and tools on temporal QA, attribution and RAG evaluation, and say how this project differs. Do this reading in Week 6.
- Include a **Limitations** section: one corpus, verifier errors, small evaluation set, single instance deployment, what you did not test.
- Include a **Future work** section: reranking, more corpora, better lineage matching, learned temporal parsing, production hardening (managed database, load balancing, monitoring).
- Resume bullets should be written last, from the final results, for example: "Built X using A and B; measured Y on N questions." Fill the blanks only with real measurements.

---

## 18. Open decisions

Resolve these early. Record each outcome in `docs/decisions.md`.

| # | Decision | Needed by | Notes |
|---|---|---|---|
| O1 | Corpus (documentation repo) | Week 1 | Criteria: permissive license, long history, frequent factual changes (limits, defaults, versions), structured text, size manageable. Count changed facts across a candidate commit range before choosing |
| O2 | Commit range and history policy | Week 2 | First-parent history or all commits |
| O3 | LLM provider and model | Week 3 | Free tier hosted vs local. Must support JSON output reliably |
| O4 | Embedding model | Week 3 | Small, 384-dim class. Compare two on the 20-query hand set |
| O5 | NLI model | Week 7 | Compare at least two candidates on the labelled set |
| O6 | Chunk size and splitting policy | Week 3 | Start with section-based, split above a token limit |
| O7 | Server instance type and domain | Week 9 | Depends on AWS plan and memory needs |
| O8 | Use of reranker | Week 6 | Only if retrieval recall is the bottleneck |

---

## 19. Appendix

### A. Failure taxonomy (to copy into `docs/`)

| Code | Failure | Example |
|---|---|---|
| F1 | Wrong version retrieved | Answers with 2024 value for a 2023 question |
| F2 | Mixed versions in context | Context holds both values, model blends them |
| F3 | Temporal parse error | "last year" resolved to the wrong year |
| F4 | Retrieval miss | Right version exists but is not in the top K |
| F5 | Unfaithful claim | Claim not supported by the cited chunk |
| F6 | Faithful but stale | Claim supported, chunk not valid at as-of date |
| F7 | Citation error | Cites a chunk that was not provided or does not contain the fact |
| F8 | Verifier error | NLI says entailed or not entailed incorrectly |
| F9 | Over-abstention | Refuses an answerable question |
| F10 | Under-abstention | Answers an unanswerable question |

### B. Labelling matrix

| Claim entailed by cited chunk | Chunk valid at as-of | Final label |
|---|---|---|
| Yes | Yes | `supported_current` |
| Yes | No | `supported_outdated` |
| No | Yes or No | `unsupported` |

### C. Starting hyperparameters (all tunable, record changes)

| Parameter | Starting value |
|---|---|
| Per-branch retrieval depth | 20 |
| RRF constant k | 60 |
| Final context chunks | 5 |
| Chunk split threshold | about 400 tokens |
| NLI entailment threshold | tuned on calibration set |
| Revision retries | 1 |
| LLM temperature | 0 for extraction and verification, low for generation |

### D. Environment variables (`.env.example`)

```
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/trace
LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=
EMBEDDING_MODEL=
NLI_MODEL=
LOG_LEVEL=INFO
RATE_LIMIT_PER_MIN=30
```

### E. Daily and weekly working checklist

- [ ] Pull latest, run tests before starting.
- [ ] Work on one module task at a time, commit small changes with clear messages.
- [ ] Add tests with the code, not later.
- [ ] End of week: update this file's checkboxes, `docs/devlog.md`, and `docs/decisions.md`.

### F. Suggested reading list (do during Weeks 6 to 8)

- pgvector documentation (indexes, filtering, iterative scans).
- PostgreSQL range types and exclusion constraints.
- Papers and write-ups on temporal question answering, attribution/citation evaluation in RAG, and NLI-based factual consistency checking. Search for current surveys, since the field moves quickly.
- Documentation of the NLI and embedding models you choose (input limits, known weaknesses).
