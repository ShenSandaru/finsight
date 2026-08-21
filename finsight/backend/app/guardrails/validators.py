"""Guardrails Deterministic Validators for Financial Responses (Sprint 9.2)."""

import logging
import math
import re
from uuid import UUID

from app.core.config import get_settings
from app.services.retrieval_service import RetrievalResult
from app.services.rag_service import SourceCitation, INSUFFICIENT_EVIDENCE_ANSWER
from app.agents.state import FinancialFinding, CitationAuditResult

logger = logging.getLogger("finsight.guardrails.validators")
settings = get_settings()


class StructureValidator:
    """Validates basic response structure, non-emptiness, and bounds."""

    @classmethod
    def validate_answer(cls, answer: str | None) -> tuple[bool, str, str | None]:
        if answer is None:
            return False, "", "Response answer field is None"
        
        stripped = answer.strip()
        if not stripped:
            return False, "", "Response answer is empty or whitespace"
        
        if len(stripped) > settings.GUARDRAILS_MAX_RESPONSE_LENGTH:
            return False, stripped[:settings.GUARDRAILS_MAX_RESPONSE_LENGTH], f"Answer exceeds max length ({len(stripped)} > {settings.GUARDRAILS_MAX_RESPONSE_LENGTH})"
        
        return True, stripped, None


class FinancialFindingValidator:
    """Validates financial findings against retrieved PostgreSQL chunk records."""

    @classmethod
    def validate_findings(
        cls,
        findings: list[FinancialFinding],
        retrieved_chunks: list[RetrievalResult],
    ) -> tuple[list[FinancialFinding], list[str]]:
        valid_chunk_ids = {c.chunk_id for c in retrieved_chunks}
        valid_findings: list[FinancialFinding] = []
        violations: list[str] = []

        for f in findings:
            # 1. Must have source chunk IDs
            if not f.source_chunk_ids:
                violations.append(f"Finding '{f.metric}' ({f.period}) lacks source_chunk_ids")
                continue

            # 2. Every source chunk ID must exist in retrieved evidence
            missing_ids = [cid for cid in f.source_chunk_ids if cid not in valid_chunk_ids]
            if missing_ids:
                violations.append(f"Finding '{f.metric}' ({f.period}) references unavailable chunk IDs: {missing_ids}")
                continue

            # 3. Numeric validity (not NaN or Inf)
            if math.isnan(f.value) or math.isinf(f.value):
                violations.append(f"Finding '{f.metric}' ({f.period}) has invalid numeric value {f.value}")
                continue

            # 4. Mathematical bounds for percentages (e.g. margin, growth)
            if f.unit == "%" and (f.value < -1000.0 or f.value > 10000.0):
                violations.append(f"Finding '{f.metric}' ({f.period}) percentage {f.value}% is outside reasonable financial bounds")
                continue

            valid_findings.append(f)

        return valid_findings, violations


class CitationValidator:
    """Validates citation references and enforces citation integrity."""

    @classmethod
    def validate_citations(
        cls,
        citations: list[SourceCitation],
        retrieved_chunks: list[RetrievalResult],
        answer_text: str,
    ) -> tuple[list[SourceCitation], list[str]]:
        valid_chunk_ids = {c.chunk_id for c in retrieved_chunks}
        valid_citations: list[SourceCitation] = []
        violations: list[str] = []

        for cit in citations:
            if cit.chunk_id not in valid_chunk_ids:
                violations.append(f"Citation references unretrieved chunk ID '{cit.chunk_id}'")
                continue
            valid_citations.append(cit)

        # Check for citation numbers in text exceeding available valid citations
        cited_indices = [int(m) for m in re.findall(r"\[SOURCE\s+(\d+)\]", answer_text, flags=re.IGNORECASE)]
        for idx in cited_indices:
            if idx < 1 or idx > len(valid_citations):
                violations.append(f"Answer cites [SOURCE {idx}] but only {len(valid_citations)} valid source citations exist")

        return valid_citations, violations


class GroundingConsistencyValidator:
    """Verifies that grounded=True is only allowed when valid retrieved evidence exists."""

    @classmethod
    def validate_grounding(
        cls,
        grounded: bool,
        retrieved_chunks: list[RetrievalResult],
        valid_citations: list[SourceCitation],
    ) -> tuple[bool, str | None]:
        has_evidence = len(retrieved_chunks) > 0 and len(valid_citations) > 0

        if grounded and not has_evidence:
            return False, "Response claims grounded=True but no valid retrieved evidence or citations exist"

        if not grounded and has_evidence:
            # If evidence was retrieved but flagged ungrounded (e.g. audit failed), consistent with controlled fallback
            return True, None

        return True, None
