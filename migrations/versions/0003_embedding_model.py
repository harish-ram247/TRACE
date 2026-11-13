"""Record which model produced each embedding.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN embedding_model TEXT")
    op.execute(
        "ALTER TABLE chunks ADD CONSTRAINT chunks_embedding_has_model "
        "CHECK (embedding IS NULL OR embedding_model IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_embedding_has_model")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding_model")
