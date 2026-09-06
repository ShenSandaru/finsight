"""Add users, user_sessions, and resource ownership backfilled to system user

Revision ID: 0006_add_users_and_ownership
Revises: 0005_enhance_reports_schema
Create Date: 2026-09-05 12:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_add_users_and_ownership"
down_revision: Union[str, None] = "0005_enhance_reports_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="google"),
        sa.Column("provider_sub", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider", "provider_sub", name="uq_users_provider_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # 2. Create user_sessions table
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_session_token_hash", "user_sessions", ["session_token_hash"], unique=True)
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    # 3. Seed default system migration user
    op.execute(
        f"""
        INSERT INTO users (id, email, name, provider, provider_sub, is_active)
        VALUES ('{SYSTEM_USER_ID}', 'system@finsight.local', 'System Migration User', 'system', 'system-default', true)
        ON CONFLICT (provider, provider_sub) DO NOTHING;
        """
    )

    # 4. Add user_id column as nullable first to documents, conversation_sessions, reports
    op.add_column("documents", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("conversation_sessions", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("reports", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))

    # 5. Backfill existing records to SYSTEM_USER_ID
    op.execute(f"UPDATE documents SET user_id = '{SYSTEM_USER_ID}' WHERE user_id IS NULL;")
    op.execute(f"UPDATE conversation_sessions SET user_id = '{SYSTEM_USER_ID}' WHERE user_id IS NULL;")
    op.execute(f"UPDATE reports SET user_id = '{SYSTEM_USER_ID}' WHERE user_id IS NULL;")

    # 6. Enforce NOT NULL and Foreign Key constraints
    op.alter_column("documents", "user_id", nullable=False)
    op.create_foreign_key("fk_documents_user_id", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.alter_column("conversation_sessions", "user_id", nullable=False)
    op.create_foreign_key("fk_conversation_sessions_user_id", "conversation_sessions", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_conversation_sessions_user_id", "conversation_sessions", ["user_id"])

    op.alter_column("reports", "user_id", nullable=False)
    op.create_foreign_key("fk_reports_user_id", "reports", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_reports_user_id", "reports", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("fk_reports_user_id", "reports", type_="foreignkey")
    op.drop_index("ix_reports_user_id", "reports")
    op.drop_column("reports", "user_id")

    op.drop_constraint("fk_conversation_sessions_user_id", "conversation_sessions", type_="foreignkey")
    op.drop_index("ix_conversation_sessions_user_id", "conversation_sessions")
    op.drop_column("conversation_sessions", "user_id")

    op.drop_constraint("fk_documents_user_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_user_id", "documents")
    op.drop_column("documents", "user_id")

    op.drop_table("user_sessions")
    op.drop_table("users")
