"""Add conversation_sessions and conversation_messages tables

Revision ID: 0004_add_conversation_memory
Revises: 0003_add_hnsw_index
Create Date: 2026-08-21 19:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0004_add_conversation_memory'
down_revision: Union[str, None] = '0003_add_hnsw_index'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversation_sessions table
    op.create_table(
        'conversation_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create conversation_messages table
    op.create_table(
        'conversation_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['conversation_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'ix_conversation_messages_session_id',
        'conversation_messages',
        ['session_id'],
        unique=False,
    )
    op.create_index(
        'ix_conversation_messages_created_at',
        'conversation_messages',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        'ix_conversation_messages_session_created',
        'conversation_messages',
        ['session_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_conversation_messages_session_created', table_name='conversation_messages')
    op.drop_index('ix_conversation_messages_created_at', table_name='conversation_messages')
    op.drop_index('ix_conversation_messages_session_id', table_name='conversation_messages')
    op.drop_table('conversation_messages')
    op.drop_table('conversation_sessions')
