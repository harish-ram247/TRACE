# TRACE

**T**emporal **R**etrieval with **A**ttributed **C**laim **E**vidence.

A RAG backend that knows *when* each passage was true and checks that every claim in an answer
is supported by a source that was valid on the date asked. The full design, module list, schedule
and evaluation plan are in [project_plan.md](project_plan.md).

> Status: early development (Week 1, foundation). Nothing here is evaluated yet.

## Quick start

Requirements: Python 3.11+, Docker with Compose.

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

docker compose up -d db
alembic upgrade head
pytest
uvicorn app.main:app --reload
```

No Docker? Run PostgreSQL + pgvector from Python instead, on the same address (`localhost:5433`):

```bash
pip install -e ".[localdb]"
python -m scripts.local_db start      # also: stop, status
alembic upgrade head
```

Check it is alive: `GET http://localhost:8000/health` and `GET http://localhost:8000/health/db`.

To run the API inside Docker as well: `docker compose up --build`.

## Ingesting a repository

```bash
python -m app.ingest --repo path/to/docs-repo --repo-id https://example.com/org/docs.git --check
```

Walks the first-parent history, versions every markdown section with a validity interval, and
checks the invariants. Re-running only processes new commits. The project's corpus and the exact
commands to reproduce it are in [docs/corpus.md](docs/corpus.md).

Then embed the chunks (downloads a ~67 MB model on first run) and check retrieval:

```bash
python -m app.retrieval.backfill --repo-id https://github.com/vitejs/vite
python -m scripts.retrieval_check https://github.com/vitejs/vite
```

Corpus: [Vite documentation](https://github.com/vitejs/vite), MIT License,
Copyright (c) 2019-present, VoidZero Inc. and Vite contributors.

## Asking questions

With an LLM configured in `.env` (see `.env.example`; check it with `python -m app.core.llm_check`):

```bash
uvicorn app.main:app --reload
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json"   -d '{"question": "What port did vite preview use by default in December 2021?"}'
```

The response includes the date the question was resolved to, the answer with `[S1]`-style citations,
and each cited source's validity interval. `"variant": "plain"` runs the no-time-filter baseline and
`"as_of"` overrides the parsed date.

## Project layout

See section 6 of [project_plan.md](project_plan.md).
