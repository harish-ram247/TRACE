"""Retrieval sanity check on a small hand-written query set (plan M4 acceptance).

Each line of the dataset names the section that should be retrieved, by document path and
section path, at a given as-of date. The gold chunk is the version of that section valid then.

Usage: python -m scripts.retrieval_check REPO_ID [--dataset eval/datasets/retrieval_smoke.jsonl]

This is a development check, not the project's evaluation (that is plan section 10).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.retrieval.embeddings import FastEmbedder, get_embedder
from app.retrieval.search import search

DEFAULT_DATASET = Path("eval/datasets/retrieval_smoke.jsonl")


def resolve_gold(conn, repo_id: str, item: dict) -> tuple[int, int] | None:
    row = conn.execute(
        """
        SELECT c.id, c.lineage_id FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s AND d.source_path = %s AND c.section_path = %s
          AND c.valid @> %s::timestamptz
        """,
        (repo_id, item["source_path"], item["section_path"], item["as_of"]),
    ).fetchone()
    return (row[0], row[1]) if row else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_id")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args(argv)

    items = [json.loads(line) for line in args.dataset.read_text("utf-8").splitlines() if line]
    s = get_settings()
    with_prefix = get_embedder()
    no_prefix = FastEmbedder(s.embedding_model, "", s.model_cache_dir)

    variants = {
        "hybrid, time filter": dict(embedder=with_prefix),
        "keyword only, time filter": dict(embedder=with_prefix, branches=("keyword",)),
        "vector only, time filter": dict(embedder=with_prefix, branches=("vector",)),
        "hybrid, no query prefix": dict(embedder=no_prefix),
        "hybrid, NO time filter": dict(embedder=with_prefix, time_filter=False),
    }

    with psycopg.connect(s.psycopg_dsn, autocommit=True) as conn:
        golds = {}
        for item in items:
            gold = resolve_gold(conn, args.repo_id, item)
            if gold is None:
                print(f"dataset error: no valid chunk for {item['id']}")
                return 1
            golds[item["id"]] = gold

        print(f"{len(items)} queries\n")
        print(f"{'variant':<28}{'R@1':>6}{'R@5':>6}{'R@10':>6}{'wrong version @1':>18}")
        for name, kwargs in variants.items():
            r1 = r5 = r10 = stale = 0
            for item in items:
                gold_id, gold_lineage = golds[item["id"]]
                as_of = datetime.fromisoformat(item["as_of"])
                hits = search(conn, item["query"], as_of, repo_id=args.repo_id, top_k=10, **kwargs)
                ids = [h.chunk_id for h in hits]
                r1 += gold_id in ids[:1]
                r5 += gold_id in ids[:5]
                r10 += gold_id in ids[:10]
                stale += bool(hits) and hits[0].lineage_id == gold_lineage and ids[0] != gold_id
            n = len(items)
            print(f"{name:<28}{r1 / n:>6.2f}{r5 / n:>6.2f}{r10 / n:>6.2f}{stale:>18}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
