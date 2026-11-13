"""How much does filtering by validity hurt approximate (HNSW) vector search?

For sampled queries at several as-of dates, compares three vector-branch modes against an
exact scan:
- index:     plain HNSW scan, then filter (can return fewer rows than asked for)
- iterative: pgvector iterative scan, keeps scanning until enough rows pass the filter
- exact:     no index, the ground truth

Usage: python -m scripts.ann_filter_check REPO_ID [--queries 30] [--n 20]
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from datetime import UTC, datetime

import psycopg

from app.core.config import get_settings
from app.retrieval.embeddings import get_embedder
from app.retrieval.search import _filters, vector_candidates

DATES = ["2021-06-01", "2022-06-01", "2023-06-01", "2024-06-01", "2025-06-01", "2026-11-01"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_id")
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    embedder = get_embedder()
    with psycopg.connect(get_settings().psycopg_dsn, autocommit=True) as conn:
        texts = [
            r[0]
            for r in conn.execute(
                """
                SELECT c.text FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE d.repo_url = %s ORDER BY c.id
                """,
                (args.repo_id,),
            ).fetchall()
        ]
        total = len(texts)
        rng = random.Random(args.seed)
        queries = [" ".join(t.split()[:15]) for t in rng.sample(texts, args.queries)]
        vectors = [embedder.embed_query(q) for q in queries]

        print(f"{total} chunk versions; {args.queries} queries; top {args.n}")
        header = f"{'as_of':<12}{'valid':>8}{'index rows':>12}{'index rec':>11}"
        print(header + f"{'iter rows':>11}{'iter rec':>10}")
        for date in DATES:
            as_of = datetime.fromisoformat(date).replace(tzinfo=UTC)
            where, params = _filters(as_of, args.repo_id, time_filter=True)
            valid = conn.execute(
                f"""
                SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id
                WHERE true {where}
                """,
                params,
            ).fetchone()[0]
            rows = {"index": [], "iterative": []}
            recall = {"index": [], "iterative": []}
            for qv in vectors:
                exact = set(vector_candidates(conn, qv, where, params, args.n, mode="exact"))
                for mode in ("index", "iterative"):
                    got = vector_candidates(conn, qv, where, params, args.n, mode=mode)
                    rows[mode].append(len(got))
                    recall[mode].append(len(exact & set(got)) / len(exact) if exact else 1.0)
            print(
                f"{date:<12}{valid:>8}"
                f"{statistics.mean(rows['index']):>12.1f}{statistics.mean(recall['index']):>11.2f}"
                f"{statistics.mean(rows['iterative']):>11.1f}"
                f"{statistics.mean(recall['iterative']):>10.2f}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
