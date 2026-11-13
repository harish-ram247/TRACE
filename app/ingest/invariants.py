"""Consistency checks for ingested data (project_plan.md section 7.3).

Overlapping versions of one lineage and empty text are already rejected by the database.
These checks cover the rules a constraint cannot express.
"""

from __future__ import annotations

import psycopg


def check_invariants(conn: psycopg.Connection, repo_id: str) -> list[str]:
    problems: list[str] = []

    rows = conn.execute(
        """
        SELECT c.id, p.id FROM chunks c
        JOIN chunks p ON p.id = c.supersedes_id
        JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s
          AND (upper(p.valid) IS DISTINCT FROM lower(c.valid) OR p.lineage_id <> c.lineage_id)
        """,
        (repo_id,),
    ).fetchall()
    problems += [
        f"chunk {c} does not start exactly where its predecessor {p} ended" for c, p in rows
    ]

    rows = conn.execute(
        """
        SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s AND NOT upper_inf(c.valid) AND c.removed_commit IS NULL
        """,
        (repo_id,),
    ).fetchall()
    problems += [f"closed chunk {r[0]} has no removed_commit" for r in rows]

    rows = conn.execute(
        """
        SELECT c.document_id, c.section_path, count(*) FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.repo_url = %s AND upper_inf(c.valid)
        GROUP BY c.document_id, c.section_path HAVING count(*) > 1
        """,
        (repo_id,),
    ).fetchall()
    problems += [f"document {d}: {n} open chunks for path {p!r}" for d, p, n in rows]

    return problems
