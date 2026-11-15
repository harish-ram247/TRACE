"""Admin endpoints: queue an ingestion job, check a job. Protected by X-Admin-Token.

With no ADMIN_TOKEN configured these endpoints are disabled (403), so a fresh deployment is
closed by default. The worker (python -m app.jobs.worker) does the actual work.
"""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.pg import get_conn
from app.jobs import queue

router = APIRouter(tags=["admin"])


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().admin_token.get_secret_value()
    if not expected:
        raise HTTPException(403, "admin endpoints are disabled (no ADMIN_TOKEN configured)")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "missing or wrong X-Admin-Token")


class IngestRequest(BaseModel):
    repo_path: str = Field(min_length=1, max_length=300, description="relative to INGEST_ROOT")
    repo_id: str = Field(min_length=1, max_length=300)
    until: str = Field(default="HEAD", max_length=100, pattern=r"^[A-Za-z0-9._/^~-]+$")
    paths: list[str] = Field(default_factory=list, max_length=20)


class JobOut(BaseModel):
    id: int
    type: str
    status: str
    attempts: int
    max_attempts: int
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


@router.post("/ingest", status_code=202, dependencies=[Depends(require_admin)])
def ingest(
    req: IngestRequest, conn: Annotated[psycopg.Connection, Depends(get_conn)]
) -> dict[str, int]:
    job_id = queue.enqueue(conn, "ingest", req.model_dump())
    return {"job_id": job_id}


@router.get("/jobs/{job_id}", response_model=JobOut, dependencies=[Depends(require_admin)])
def job_status(job_id: int, conn: Annotated[psycopg.Connection, Depends(get_conn)]) -> JobOut:
    job = queue.get(conn, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return JobOut(**{k: v for k, v in job.items() if k != "payload"})
