"""Guardrails AI Output Validation Schemas for FinSight (Sprint 9.2)."""

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.services.rag_service import SourceCitation
from app.agents.state import FinancialFinding, CitationAuditResult


class GuardrailsValidationResult(BaseModel):
    """Structured result produced by the Guardrails Validation Layer."""
    passed: bool = Field(..., description="True if output satisfies all structural, grounding, and citation guards")
    validated_answer: str = Field(..., description="Cleaned and validated answer safe for user presentation")
    validated_citations: list[SourceCitation] = Field(
        default_factory=list,
        description="Verified source citations backed by retrieved chunks",
    )
    validated_findings: list[FinancialFinding] = Field(
        default_factory=list,
        description="Verified financial findings backed by evidence",
    )
    grounded: bool = Field(..., description="Grounded status consistent with available evidence")
    violation_reasons: list[str] = Field(
        default_factory=list,
        description="Safe diagnostic violation messages if validation checks failed",
    )


class ResearchResponse(BaseModel):
    """Strict structured response contract for research answers."""
    answer: str = Field(..., description="Grounded answer text with validated citations")
    citations: list[SourceCitation] = Field(
        default_factory=list,
        description="Valid source citations",
    )
    grounded: bool = Field(..., description="Whether answer is grounded in retrieved chunks")
    findings: list[FinancialFinding] = Field(
        default_factory=list,
        description="Verified financial metrics and ratios",
    )
