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

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sources: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    report_type: Mapped[str] = mapped_column(
        String(50),
        default="analysis",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, type='{self.report_type}')>"