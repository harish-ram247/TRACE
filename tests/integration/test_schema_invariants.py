"""Schema-level guarantees from project_plan.md section 7.3.

Requires a migrated database: `docker compose up -d db` then `alembic upgrade head`.
"""

import psycopg
import pytest

pytestmark = pytest.mark.integration

INSERT_DOC = "INSERT INTO documents (source_path) VALUES ('docs/limits.md') RETURNING id"
INSERT_CHUNK = """
    INSERT INTO chunks (lineage_id, document_id, section_path, text, content_hash, valid)
    VALUES (%s, %s, 'limits', %s, %s, tstzrange(%s, %s))
    RETURNING id
"""


def _doc(conn) -> int:
    return conn.execute(INSERT_DOC).fetchone()[0]


def _chunk(conn, lineage, doc, text, start, end):
    return conn.execute(INSERT_CHUNK, (lineage, doc, text, f"h-{text}", start, end)).fetchone()[0]


def test_required_extensions_are_installed(pg):
    rows = pg.execute(
        "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'btree_gist')"
    ).fetchall()
    assert {r[0] for r in rows} == {"vector", "btree_gist"}


def test_adjacent_versions_of_one_lineage_are_allowed(pg):
    doc = _doc(pg)
    _chunk(pg, 1, doc, "100 per minute", "2023-01-01", "2024-02-01")
    _chunk(pg, 1, doc, "500 per minute", "2024-02-01", None)


def test_overlapping_versions_of_one_lineage_are_rejected(pg):
    doc = _doc(pg)
    _chunk(pg, 2, doc, "100 per minute", "2023-01-01", "2024-03-01")
    with pytest.raises(psycopg.errors.ExclusionViolation):
        _chunk(pg, 2, doc, "500 per minute", "2024-02-01", None)


def test_overlap_across_different_lineages_is_allowed(pg):
    doc = _doc(pg)
    _chunk(pg, 3, doc, "alpha", "2023-01-01", None)
    _chunk(pg, 4, doc, "beta", "2023-01-01", None)


def test_empty_validity_range_is_rejected(pg):
    doc = _doc(pg)
    with pytest.raises(psycopg.errors.CheckViolation):
        _chunk(pg, 5, doc, "x", "2023-01-01", "2023-01-01")


def test_blank_text_is_rejected(pg):
    doc = _doc(pg)
    with pytest.raises(psycopg.errors.CheckViolation):
        _chunk(pg, 6, doc, "   ", "2023-01-01", None)


def test_validity_filter_returns_the_version_valid_on_a_date(pg):
    doc = _doc(pg)
    _chunk(pg, 7, doc, "limit is 100", "2023-01-01", "2024-02-01")
    _chunk(pg, 7, doc, "limit is 500", "2024-02-01", None)

    def valid_text(as_of):
        row = pg.execute(
            "SELECT text FROM chunks WHERE lineage_id = 7 AND valid @> %s::timestamptz",
            (as_of,),
        ).fetchone()
        return row[0] if row else None

    assert valid_text("2023-06-01") == "limit is 100"
    assert valid_text("2024-02-01") == "limit is 500"  # boundary belongs to the newer version
    assert valid_text("2025-01-01") == "limit is 500"
    assert valid_text("2022-01-01") is None
