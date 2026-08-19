"""add processing_error to documents

Revision ID: 0002_add_processing_error
Revises: 0001_initial_schema
Create Date: 2026-08-19 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_add_processing_error'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('processing_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'processing_error')
