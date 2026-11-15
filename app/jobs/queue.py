"""A small PostgreSQL job queue (plan D7: no Redis).

- enqueue() inserts a job
- claim() takes the oldest runnable job with FOR UPDATE SKIP LOCKED, so several workers never take
  the same job
- complete() / fail() record the outcome; a failed job is retried with exponential backoff until
  max_attempts, then marked failed
- requeue_stale() returns jobs whose worker died mid-run (locked too long) to the queue
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

import psycopg
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class Job:
    id: int
    type: str
    payload: dict
    attempts: int
    max_attempts: int


def enqueue(conn: psycopg.Connection, job_type: str, payload: dict, max_attempts: int = 3) -> int:
    return conn.execute(
        "INSERT INTO jobs (type, payload, max_attempts) VALUES (%s, %s, %s) RETURNING id",
        (job_type, Jsonb(payload), max_attempts),
    ).fetchone()[0]


def claim(conn: psycopg.Connection) -> Job | None:
    with conn.transaction():
        row = conn.execute(
            """
            SELECT id, type, payload, attempts, max_attempts FROM jobs
            WHERE status = 'queued' AND run_after <= now()
            ORDER BY run_after, id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """
            UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_at = now(),
                            updated_at = now()
            WHERE id = %s
            """,
            (row[0],),
        )
    payload = row[2] if isinstance(row[2], dict) else json.loads(row[2])
    return Job(row[0], row[1], payload, row[3] + 1, row[4])


def complete(conn: psycopg.Connection, job_id: int, result: dict) -> None:
    conn.execute(
        """
        UPDATE jobs SET status = 'done', result = %s, error = NULL, locked_at = NULL,
                        updated_at = now()
        WHERE id = %s
        """,
        (Jsonb(result), job_id),
    )


def fail(conn: psycopg.Connection, job: Job, error: str, base_delay_s: int = 30) -> str:
    """Retry later if attempts remain, otherwise mark failed. Returns the new status."""
    if job.attempts < job.max_attempts:
        delay = timedelta(seconds=base_delay_s * 2 ** (job.attempts - 1))
        conn.execute(
            """
            UPDATE jobs SET status = 'queued', run_after = now() + %s, error = %s,
                            locked_at = NULL, updated_at = now()
            WHERE id = %s
            """,
            (delay, error[:2000], job.id),
        )
        return "queued"
    conn.execute(
        """
        UPDATE jobs SET status = 'failed', error = %s, locked_at = NULL, updated_at = now()
        WHERE id = %s
        """,
        (error[:2000], job.id),
    )
    return "failed"


def requeue_stale(conn: psycopg.Connection, older_than: timedelta = timedelta(hours=1)) -> int:
    """Jobs left 'running' by a worker that died are put back in the queue."""
    return conn.execute(
        """
        UPDATE jobs SET status = 'queued', locked_at = NULL, updated_at = now(),
                        error = coalesce(error, '') || ' [requeued: worker stopped]'
        WHERE status = 'running' AND locked_at < now() - %s
        """,
        (older_than,),
    ).rowcount


def get(conn: psycopg.Connection, job_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id, type, payload, status, attempts, max_attempts, result, error,
               created_at, updated_at
        FROM jobs WHERE id = %s
        """,
        (job_id,),
    ).fetchone()
    if row is None:
        return None
    keys = ["id", "type", "payload", "status", "attempts", "max_attempts", "result", "error",
            "created_at", "updated_at"]  # fmt: skip
    return dict(zip(keys, row, strict=True))
