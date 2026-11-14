"""Express "no overlapping versions per lineage" without the btree_gist extension.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14

The original constraint was EXCLUDE USING gist (lineage_id WITH =, valid WITH &&), which needs
btree_gist for the bigint equality. Some Postgres builds (for example the one bundled in
pgserver, used when Docker is unavailable) do not ship btree_gist. A degenerate integer range
int8range(id, id, '[]') overlaps another exactly when the ids are equal, so the rule is the
same and needs only built-in operator classes.

Migration 0001 was edited to create the new constraint directly on fresh databases. This
migration converts databases that were created with the old 0001.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_lineage_id_valid_excl")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chunks_no_overlapping_versions'
            ) THEN
                ALTER TABLE chunks ADD CONSTRAINT chunks_no_overlapping_versions
                    EXCLUDE USING gist (
                        int8range(lineage_id, lineage_id, '[]') WITH &&, valid WITH &&
                    );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    pass  # the new constraint enforces the same rule; nothing to undo
