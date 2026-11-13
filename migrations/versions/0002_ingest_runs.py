"""Ingest run tracking, used for progress, resume and idempotent re-runs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ingest_runs (
            id                BIGSERIAL PRIMARY KEY,
            repo_url          TEXT NOT NULL,
            repo_ref          TEXT,
            started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at       TIMESTAMPTZ,
            status            TEXT NOT NULL DEFAULT 'running'
                              CHECK (status IN ('running', 'done', 'failed')),
            commits_processed INTEGER NOT NULL DEFAULT 0,
            -- Progress marker, updated in the same transaction as each commit's changes.
            last_commit       TEXT,
            last_effective_at TIMESTAMPTZ,
            error             TEXT
        )
        """
    )
    op.execute("CREATE INDEX ingest_runs_repo_idx ON ingest_runs (repo_url, id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ingest_runs")
