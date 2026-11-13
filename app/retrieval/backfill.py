"""Embed every chunk that has no embedding yet.

Idempotent and resumable: each batch is committed on its own, and only NULL embeddings are
selected. Run after ingestion:

    python -m app.retrieval.backfill --repo-id https://github.com/vitejs/vite
"""

from __future__ import annotations

import argparse
import sys
import time

import psycopg
from pgvector.psycopg import register_vector

from app.core.config import get_settings
from app.retrieval.embeddings import Embedder, HashEmbedder, get_embedder, passage_text


class DimensionMismatch(RuntimeError):
    pass


def column_dimension(conn: psycopg.Connection) -> int:
    return conn.execute(
        """
        SELECT atttypmod FROM pg_attribute
        WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'
        """
    ).fetchone()[0]


def embed_missing(
    conn: psycopg.Connection,
    embedder: Embedder,
    repo_id: str | None = None,
    batch_size: int = 64,
) -> int:
    register_vector(conn)
    if (dim := column_dimension(conn)) != embedder.dim:
        raise DimensionMismatch(
            f"chunks.embedding is vector({dim}) but {embedder.name} produces {embedder.dim}"
        )

    repo_clause = "AND d.repo_url = %(repo)s" if repo_id else ""
    total = 0
    while True:
        with conn.transaction():
            rows = conn.execute(
                f"""
                SELECT c.id, c.section_path, c.text
                FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE c.embedding IS NULL {repo_clause}
                ORDER BY c.id LIMIT %(n)s
                FOR UPDATE OF c SKIP LOCKED
                """,
                {"repo": repo_id, "n": batch_size},
            ).fetchall()
            if not rows:
                break
            vectors = embedder.embed_passages([passage_text(p, t) for _, p, t in rows])
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE chunks SET embedding = %s, embedding_model = %s WHERE id = %s",
                    [(v, embedder.name, cid) for v, (cid, _, _) in zip(vectors, rows, strict=True)],
                )
        total += len(rows)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed chunks that have no embedding.")
    parser.add_argument("--repo-id")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--fake", action="store_true", help="use the hashing embedder (offline)")
    args = parser.parse_args(argv)

    embedder = HashEmbedder() if args.fake else get_embedder()
    started = time.perf_counter()
    with psycopg.connect(get_settings().psycopg_dsn, autocommit=True) as conn:
        n = embed_missing(conn, embedder, args.repo_id, args.batch_size)
    print(f"embedded {n} chunks with {embedder.name} in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
