import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        default="Financial Research Report",
        nullable=False,
    )

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    report_type: Mapped[str] = mapped_column(
        String(50),
        default="financial_research",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )

    document_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    executive_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    findings: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    citations: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, title='{self.title}', status='{self.status}')>"