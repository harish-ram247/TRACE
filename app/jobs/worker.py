"""Background worker: runs queued jobs (currently: ingesting and embedding a repository).

Usage: python -m app.jobs.worker [--once] [--fake-embeddings]

The ingest job only accepts repository paths inside settings.ingest_root (data/corpus by
default), so an API caller cannot make the server read arbitrary folders.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ingest.service import ingest_repo
from app.jobs import queue
from app.retrieval.backfill import embed_missing
from app.retrieval.embeddings import Embedder, HashEmbedder, get_embedder

log = logging.getLogger(__name__)


class JobError(RuntimeError):
    pass


def resolve_repo(path: str, root: str) -> Path:
    base = Path(root).resolve()
    repo = (base / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if base != repo and base not in repo.parents:
        raise JobError(f"repository path must be inside {base}")
    if not (repo / ".git").exists() and not (repo / "HEAD").exists():
        raise JobError(f"not a git repository: {repo}")
    return repo


def handle_ingest(conn: psycopg.Connection, payload: dict, embedder: Embedder) -> dict:
    s = get_settings()
    repo = resolve_repo(payload["repo_path"], s.ingest_root)
    result = ingest_repo(
        conn,
        repo,
        payload["repo_id"],
        until=payload.get("until", "HEAD"),
        pathspecs=payload.get("paths", []),
    )
    embedded = embed_missing(conn, embedder, payload["repo_id"])
    return {
        "commits_seen": result.commits_seen,
        "chunks_added": result.chunks_added,
        "chunks_closed": result.chunks_closed,
        "embedded": embedded,
    }


HANDLERS: dict[str, Callable[[psycopg.Connection, dict, Embedder], dict]] = {
    "ingest": handle_ingest,
}


def run_once(conn: psycopg.Connection, embedder: Embedder) -> int | None:
    """Run one job if there is one. Returns its id, or None when the queue is empty."""
    job = queue.claim(conn)
    if job is None:
        return None
    log.info("job %s (%s) attempt %s/%s", job.id, job.type, job.attempts, job.max_attempts)
    try:
        handler = HANDLERS.get(job.type)
        if handler is None:
            raise JobError(f"unknown job type {job.type!r}")
        queue.complete(conn, job.id, handler(conn, job.payload, embedder))
    except JobError as exc:  # bad input: retrying will not help
        conn.execute(
            "UPDATE jobs SET status = 'failed', error = %s, locked_at = NULL, updated_at = now() "
            "WHERE id = %s",
            (str(exc), job.id),
        )
    except Exception as exc:  # transient or unexpected: retry with backoff
        log.warning("job %s failed: %s", job.id, exc)
        queue.fail(conn, job, f"{exc}\n{traceback.format_exc(limit=3)}")
    return job.id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run at most one job, then exit")
    parser.add_argument("--fake-embeddings", action="store_true")
    parser.add_argument("--poll", type=float, default=5.0, help="seconds between empty polls")
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)
    embedder = HashEmbedder() if args.fake_embeddings else get_embedder()

    with psycopg.connect(get_settings().psycopg_dsn, autocommit=True) as conn:
        if n := queue.requeue_stale(conn):
            log.info("requeued %s stale jobs", n)
        while True:
            job_id = run_once(conn, embedder)
            if args.once:
                return 0
            if job_id is None:
                time.sleep(args.poll)


if __name__ == "__main__":
    sys.exit(main())
