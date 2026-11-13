"""Command line: python -m app.ingest --repo PATH [--repo-id ID] [--until REV] [--check]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ingest.invariants import check_invariants
from app.ingest.service import ingest_repo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a git repository's history into TRACE.")
    parser.add_argument("--repo", required=True, help="path to a local git clone")
    parser.add_argument(
        "--repo-id",
        help="stable identifier stored in the database (default: absolute repo path). "
        "Use the upstream URL so the id survives moving the clone.",
    )
    parser.add_argument("--until", default="HEAD", help="last revision to ingest (default HEAD)")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        dest="paths",
        help="only ingest markdown under this path (repeatable), e.g. --path docs/",
    )
    parser.add_argument("--max-words", type=int, default=300)
    parser.add_argument("--check", action="store_true", help="run invariant checks afterwards")
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level)
    repo = Path(args.repo).resolve()
    repo_id = args.repo_id or str(repo)

    with psycopg.connect(get_settings().psycopg_dsn, autocommit=True) as conn:
        result = ingest_repo(
            conn,
            repo,
            repo_id,
            until=args.until,
            max_words=args.max_words,
            pathspecs=args.paths,
        )
        print(
            f"run {result.run_id}: {result.commits_seen} commits "
            f"({result.commits_changed} with doc changes), "
            f"+{result.chunks_added} chunks opened, {result.chunks_closed} closed"
        )
        if args.check:
            problems = check_invariants(conn, repo_id)
            for p in problems:
                print("INVARIANT VIOLATION:", p)
            if problems:
                return 1
            print("invariants ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
