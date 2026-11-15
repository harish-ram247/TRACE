"""Background job queue (ingestion runs outside request handlers).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE jobs (
            id           BIGSERIAL PRIMARY KEY,
            type         TEXT NOT NULL,
            payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
            status       TEXT NOT NULL DEFAULT 'queued'
                         CHECK (status IN ('queued', 'running', 'done', 'failed')),
            attempts     INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
            run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),
            locked_at    TIMESTAMPTZ,
            result       JSONB,
            error        TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX jobs_claimable_idx ON jobs (run_after) WHERE status = 'queued'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jobs")
