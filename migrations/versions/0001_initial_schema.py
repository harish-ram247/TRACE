"""Initial schema: extensions, documents, versioned chunks.

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute(
        """
        CREATE TABLE documents (
            id          BIGSERIAL PRIMARY KEY,
            source_path TEXT NOT NULL,
            repo_url    TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (repo_url, source_path)
        )
        """
    )

    # Lineage ids group the versions of the "same" passage over time.
    op.execute("CREATE SEQUENCE lineage_id_seq")

    # The embedding column is nullable and its dimension (384) assumes a small
    # sentence-transformers model. Revisit when the embedding model is chosen (plan O4).
    op.execute(
        """
        CREATE TABLE chunks (
            id                BIGSERIAL PRIMARY KEY,
            lineage_id        BIGINT NOT NULL,
            document_id       BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            section_path      TEXT NOT NULL,
            text              TEXT NOT NULL CHECK (length(btrim(text)) > 0),
            content_hash      TEXT NOT NULL CHECK (length(content_hash) > 0),
            embedding         vector(384),
            tsv               tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            valid             tstzrange NOT NULL CHECK (NOT isempty(valid)),
            introduced_commit TEXT,
            removed_commit    TEXT,
            supersedes_id     BIGINT REFERENCES chunks(id),
            -- No two versions of one lineage may be valid at the same time.
            EXCLUDE USING gist (lineage_id WITH =, valid WITH &&)
        )
        """
    )
    op.execute("CREATE INDEX chunks_valid_gist ON chunks USING gist (valid)")
    op.execute("CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv)")
    op.execute("CREATE INDEX chunks_emb_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX chunks_document_idx ON chunks (document_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP SEQUENCE IF EXISTS lineage_id_seq")
    op.execute("DROP TABLE IF EXISTS documents")
    # Extensions are left installed on purpose; other databases objects may use them.
