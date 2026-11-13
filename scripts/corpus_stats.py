"""Compare ingested corpora: how much factual change do they contain?

Usage: python -m scripts.corpus_stats REPO_ID [REPO_ID ...]

"Numeric change" is a rough proxy for a factual change: two consecutive versions of a section
whose sets of numbers differ (limits, defaults, version numbers). It also counts some noise such
as renumbered lists, so treat the numbers as a ranking aid, not as ground truth.
"""

from __future__ import annotations

import re
import statistics
import sys
from collections import defaultdict

import psycopg

from app.core.config import get_settings

_NUMBER = re.compile(r"\d+(?:\.\d+)*")


def numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def stats_for(conn: psycopg.Connection, repo_id: str) -> dict:
    rows = conn.execute(
        """
        SELECT c.lineage_id, c.id, c.supersedes_id, c.text, lower(c.valid)
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s ORDER BY c.lineage_id, lower(c.valid)
        """,
        (repo_id,),
    ).fetchall()
    docs = conn.execute(
        "SELECT count(*) FROM documents WHERE repo_url = %s", (repo_id,)
    ).fetchone()[0]

    by_lineage: dict[int, list] = defaultdict(list)
    for lineage, _id, _sup, text, start in rows:
        by_lineage[lineage].append((start, text))

    multi = [v for v in by_lineage.values() if len(v) > 1]
    numeric_transitions = 0
    lineages_with_numeric = 0
    lineages_with_two_numeric = 0
    for versions in multi:
        pairs = zip(versions, versions[1:], strict=False)
        n = sum(1 for a, b in pairs if numbers(a[1]) != numbers(b[1]))
        numeric_transitions += n
        lineages_with_numeric += n >= 1
        lineages_with_two_numeric += n >= 2

    starts = [r[4] for r in rows]
    words = [len(r[3].split()) for r in rows]
    return {
        "documents": docs,
        "chunk versions": len(rows),
        "lineages": len(by_lineage),
        "lineages with 2+ versions": len(multi),
        "lineages with a numeric change": lineages_with_numeric,
        "lineages with 2+ numeric changes": lineages_with_two_numeric,
        "numeric transitions": numeric_transitions,
        "first version": min(starts).date().isoformat() if starts else "-",
        "last version": max(starts).date().isoformat() if starts else "-",
        "median words per chunk": int(statistics.median(words)) if words else 0,
    }


def main(repo_ids: list[str]) -> int:
    if not repo_ids:
        print(__doc__)
        return 2
    with psycopg.connect(get_settings().psycopg_dsn) as conn:
        results = {rid: stats_for(conn, rid) for rid in repo_ids}
    keys = list(next(iter(results.values())))
    width = max(len(k) for k in keys)
    print(" " * width, *[f"{rid[-28:]:>30}" for rid in results])
    for key in keys:
        print(f"{key:<{width}}", *[f"{r[key]!s:>30}" for r in results.values()])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
