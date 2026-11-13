"""Hybrid, time-filtered retrieval.

Two branches run over the chunks valid at `as_of`:
- keyword: PostgreSQL full-text search, query terms OR-ed together, ranked by ts_rank_cd
- vector:  cosine distance on the chunk embedding (HNSW index)
Their rankings are merged with Reciprocal Rank Fusion.

`time_filter=False` searches every version ever stored. That is the "plain RAG" baseline the
evaluation compares against, not something the product should use.

Filtered approximate search: an HNSW scan filtered by validity can return fewer rows than asked
for. pgvector >= 0.8 can keep scanning ("iterative scan"), which is the default here. The
`exact` mode skips the index and is used to measure how much the approximation loses.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from app.retrieval.embeddings import Embedder

VectorMode = Literal["index", "iterative", "exact"]
Branch = Literal["keyword", "vector"]


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    lineage_id: int
    source_path: str
    section_path: str
    text: str
    valid_from: datetime
    valid_until: datetime | None
    score: float
    keyword_rank: int | None
    vector_rank: int | None


def rrf(rankings: Iterable[list[int]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (k + rank), rank starting at 1."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores


def _filters(as_of: datetime | None, repo_id: str | None, time_filter: bool) -> tuple[str, dict]:
    clauses, params = [], {}
    if time_filter:
        if as_of is None:
            raise ValueError("as_of is required when time_filter is on")
        clauses.append("c.valid @> %(as_of)s::timestamptz")
        params["as_of"] = as_of
    if repo_id:
        clauses.append("d.repo_url = %(repo)s")
        params["repo"] = repo_id
    return "".join(f" AND {c}" for c in clauses), params


def keyword_candidates(
    conn: psycopg.Connection,
    query: str,
    where: str,
    params: dict,
    n: int,
    normalization: int = 2,
) -> list[int]:
    """Full-text candidates. `normalization` is ts_rank_cd's flag; 2 divides by document length.

    Without length normalisation, OR-ed queries favour long sections that mention many common
    words (migration guides). Chosen on the 20-query dev set (docs/devlog.md); re-check it on
    the held-out evaluation set.
    """
    rows = conn.execute(
        f"""
        SELECT c.id
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        CROSS JOIN (
            SELECT replace(plainto_tsquery('english', %(q)s)::text, '&', '|')::tsquery AS query
        ) q
        WHERE c.tsv @@ q.query {where}
        ORDER BY ts_rank_cd(c.tsv, q.query, %(norm)s) DESC, c.id
        LIMIT %(n)s
        """,
        {**params, "q": query, "n": n, "norm": normalization},
    ).fetchall()
    return [r[0] for r in rows]


def vector_candidates(
    conn: psycopg.Connection,
    query_vec: np.ndarray,
    where: str,
    params: dict,
    n: int,
    mode: VectorMode = "iterative",
    ef_search: int = 100,
) -> list[int]:
    register_vector(conn)
    # "+ 0" makes the sort expression differ from the index expression, forcing an exact scan.
    order = "(c.embedding <=> %(qv)s) + 0" if mode == "exact" else "c.embedding <=> %(qv)s"
    with conn.transaction():
        conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef_search),))
        scan = "relaxed_order" if mode == "iterative" else "off"
        conn.execute("SELECT set_config('hnsw.iterative_scan', %s, true)", (scan,))
        rows = conn.execute(
            f"""
            SELECT c.id, c.embedding <=> %(qv)s AS dist
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE c.embedding IS NOT NULL {where}
            ORDER BY {order}
            LIMIT %(n)s
            """,
            {**params, "qv": query_vec, "n": n},
        ).fetchall()
    # relaxed_order may return rows slightly out of order
    return [cid for cid, _ in sorted(rows, key=lambda r: (r[1], r[0]))]


def search(
    conn: psycopg.Connection,
    query: str,
    as_of: datetime | None,
    *,
    embedder: Embedder,
    repo_id: str | None = None,
    top_k: int = 5,
    per_branch: int = 20,
    rrf_k: int = 60,
    time_filter: bool = True,
    branches: tuple[Branch, ...] = ("keyword", "vector"),
    vector_mode: VectorMode = "iterative",
) -> list[Hit]:
    where, params = _filters(as_of, repo_id, time_filter)
    keyword = (
        keyword_candidates(conn, query, where, params, per_branch) if "keyword" in branches else []
    )
    vector = (
        vector_candidates(conn, embedder.embed_query(query), where, params, per_branch, vector_mode)
        if "vector" in branches
        else []
    )

    fused = rrf([keyword, vector], k=rrf_k)
    top = sorted(fused, key=lambda cid: (-fused[cid], cid))[:top_k]
    if not top:
        return []

    rows = conn.execute(
        """
        SELECT c.id, c.lineage_id, d.source_path, c.section_path, c.text,
               lower(c.valid), upper(c.valid)
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.id = ANY(%s)
        """,
        (top,),
    ).fetchall()
    by_id = {r[0]: r for r in rows}
    kw_rank = {cid: i for i, cid in enumerate(keyword, start=1)}
    vec_rank = {cid: i for i, cid in enumerate(vector, start=1)}
    return [
        Hit(*by_id[cid], fused[cid], kw_rank.get(cid), vec_rank.get(cid))
        for cid in top
        if cid in by_id
    ]
