"""Read-only views of the versioned corpus: one chunk, or every version of a section."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.pg import get_conn

router = APIRouter(tags=["corpus"])

_SELECT = """
    SELECT c.id, c.lineage_id, d.source_path, c.section_path, c.text, lower(c.valid),
           upper(c.valid), c.introduced_commit, c.removed_commit, c.supersedes_id
    FROM chunks c JOIN documents d ON d.id = c.document_id
"""


class ChunkOut(BaseModel):
    id: int
    lineage_id: int
    source_path: str
    section_path: str
    text: str
    valid_from: datetime
    valid_until: datetime | None
    introduced_commit: str | None
    removed_commit: str | None
    supersedes_id: int | None


class LineageOut(BaseModel):
    lineage_id: int
    versions: list[ChunkOut]


def _chunk(row) -> ChunkOut:
    keys = ChunkOut.model_fields.keys()
    return ChunkOut(**dict(zip(keys, row, strict=True)))


@router.get("/chunks/{chunk_id}", response_model=ChunkOut)
def get_chunk(chunk_id: int, conn: Annotated[psycopg.Connection, Depends(get_conn)]) -> ChunkOut:
    row = conn.execute(
        _SELECT + " WHERE c.id = %s AND d.repo_url = %s",
        (chunk_id, get_settings().corpus_repo_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "chunk not found")
    return _chunk(row)


@router.get("/lineages/{lineage_id}", response_model=LineageOut)
def get_lineage(
    lineage_id: int, conn: Annotated[psycopg.Connection, Depends(get_conn)]
) -> LineageOut:
    """Every version of one section, oldest first: the section's history."""
    rows = conn.execute(
        _SELECT + " WHERE c.lineage_id = %s AND d.repo_url = %s ORDER BY lower(c.valid)",
        (lineage_id, get_settings().corpus_repo_id),
    ).fetchall()
    if not rows:
        raise HTTPException(404, "lineage not found")
    return LineageOut(lineage_id=lineage_id, versions=[_chunk(r) for r in rows])
