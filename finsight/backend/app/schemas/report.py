"""Pydantic schemas for Financial Research Reports (Sprint 10.4)."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.rag import CitationResponse


class CreateReportRequest(BaseModel):
    """Payload for submitting a new financial research report request."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Financial research question, theme, or comparative topic",
    )
    title: str | None = Field(
        None,
        max_length=255,
        description="Optional descriptive title for the generated report",
    )
    document_ids: list[uuid.UUID] | None = Field(
        None,
        description="Optional list of document UUIDs to strictly scope vector retrieval and evidence context",
    )
    report_type: str = Field(
        "financial_research",
        description="Report format type (defaults to 'financial_research')",
    )


class ReportResponse(BaseModel):
    """Complete representation of a financial research report."""
    id: uuid.UUID = Field(..., description="Unique report identifier")
    title: str = Field(..., description="Report title")
    query: str = Field(..., description="Original user research query")
    report_type: str = Field(..., description="Format classification type")
    status: str = Field(..., description="Report lifecycle status: pending, processing, completed, failed")
    document_ids: list[uuid.UUID] | None = Field(None, description="Scoped document UUIDs")
    executive_summary: str | None = Field(None, description="Grounded research synthesis")
    findings: list[dict] | None = Field(None, description="Structured audited financial findings")
    content: str | None = Field(None, description="Full formatted GitHub Flavored Markdown report")
    citations: list[CitationResponse] | None = Field(None, description="Structured source chunk citations")
    error_message: str | None = Field(None, description="Sanitized diagnostic error message on failure")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    """Paginated or bounded list of financial reports."""
    total: int = Field(..., description="Total count of reports returned")
    reports: list[ReportResponse] = Field(..., description="List of report items")
