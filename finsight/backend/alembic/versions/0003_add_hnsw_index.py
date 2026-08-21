"""Add HNSW cosine index on chunks.embedding

Revision ID: 0003_add_hnsw_index
Revises: 0002_add_processing_error
Create Date: 2026-08-21 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_add_hnsw_index'
down_revision: Union[str, None] = '0002_add_processing_error'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure vector extension is present
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create HNSW index with cosine distance operator class
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw_cosine
        ON chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw_cosine")
