"""Enhance reports schema for Sprint 10.4 structured research reports

Revision ID: 0005_enhance_reports_schema
Revises: 0004_add_conversation_memory
Create Date: 2026-08-21 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_enhance_reports_schema'
down_revision: Union[str, None] = '0004_add_conversation_memory'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to reports table
    op.add_column('reports', sa.Column('title', sa.String(length=255), nullable=False, server_default='Financial Research Report'))
    op.add_column('reports', sa.Column('document_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('reports', sa.Column('executive_summary', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('reports', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('reports', sa.Column('error_message', sa.String(length=500), nullable=True))
    op.add_column('reports', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))

    # 2. Drop old unused baseline columns if they exist, or alter existing status/report_type defaults
    # Drop response and sources columns from initial schema
    op.drop_column('reports', 'response')
    op.drop_column('reports', 'sources')

    # Update server default for status to 'pending' and report_type to 'financial_research'
    op.alter_column('reports', 'status', server_default='pending')
    op.alter_column('reports', 'report_type', server_default='financial_research')


def downgrade() -> None:
    op.add_column('reports', sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('reports', sa.Column('response', sa.Text(), nullable=False, server_default=''))
    
    op.drop_column('reports', 'updated_at')
    op.drop_column('reports', 'error_message')
    op.drop_column('reports', 'citations')
    op.drop_column('reports', 'content')
    op.drop_column('reports', 'findings')
    op.drop_column('reports', 'executive_summary')
    op.drop_column('reports', 'document_ids')
    op.drop_column('reports', 'title')

    op.alter_column('reports', 'status', server_default='completed')
    op.alter_column('reports', 'report_type', server_default='analysis')
