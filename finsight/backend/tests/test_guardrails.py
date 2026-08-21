"""Deterministic Unit & Integration Test Suite for Guardrails AI Validation Layer (Sprint 9.2)."""

import math
import uuid
import pytest

from app.services.retrieval_service import RetrievalResult
from app.services.rag_service import SourceCitation, INSUFFICIENT_EVIDENCE_ANSWER
from app.agents.state import FinancialFinding, CitationAuditResult, AuditedFinding, ResearchState
from app.guardrails.schemas import GuardrailsValidationResult, ResearchResponse
from app.guardrails.validators import (
    StructureValidator,
    FinancialFindingValidator,
    CitationValidator,
    GroundingConsistencyValidator,
)
from app.guardrails.response_guard import ResponseGuard
from app.agents.graph import FinancialResearchService


def create_sample_chunk(chunk_id: uuid.UUID | None = None, content: str = "Total Revenue in 2025 was $1,000 million.") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        chunk_type="table",
        chunk_index=0,
        page_number=1,
        similarity=0.92,
        metadata={"statement_type": "income_statement"},
    )


def create_sample_citation(chunk_id: uuid.UUID, doc_id: uuid.UUID | None = None) -> SourceCitation:
    return SourceCitation(
        chunk_id=chunk_id,
        document_id=doc_id or uuid.uuid4(),
        page_number=1,
        chunk_type="table",
        similarity=0.92,
        statement_type="income_statement",
        fiscal_periods=["2025"],
    )


class TestStructureValidator:

    def test_01_valid_answer_passes(self):
        valid, ans, err = StructureValidator.validate_answer("Revenue was $1,000 in 2025. [SOURCE 1]")
        assert valid is True
        assert err is None
        assert ans == "Revenue was $1,000 in 2025. [SOURCE 1]"

    def test_02_empty_or_none_answer_fails(self):
        valid1, _, err1 = StructureValidator.validate_answer("")
        assert valid1 is False
        assert "empty" in err1.lower()

        valid2, _, err2 = StructureValidator.validate_answer(None)
        assert valid2 is False
        assert "none" in err2.lower()

    def test_03_excessive_length_answer_truncated_and_flagged(self):
        long_ans = "A" * 15000
        valid, ans, err = StructureValidator.validate_answer(long_ans)
        assert valid is False
        assert "exceeds max length" in err


class TestFinancialFindingValidator:

    def test_04_valid_finding_with_retrieved_chunk_passes(self):
        chunk = create_sample_chunk()
        finding = FinancialFinding(
            metric="revenue",
            period="2025",
            value=1000.0,
            unit="$",
            source_chunk_ids=[chunk.chunk_id],
        )

        valid_findings, violations = FinancialFindingValidator.validate_findings(
            findings=[finding],
            retrieved_chunks=[chunk],
        )
        assert len(valid_findings) == 1
        assert len(violations) == 0

    def test_05_finding_without_source_chunk_id_rejected(self):
        chunk = create_sample_chunk()
        finding = FinancialFinding(
            metric="revenue",
            period="2025",
            value=1000.0,
            unit="$",
            source_chunk_ids=[],
        )

        valid_findings, violations = FinancialFindingValidator.validate_findings(
            findings=[finding],
            retrieved_chunks=[chunk],
        )
        assert len(valid_findings) == 0
        assert len(violations) == 1
        assert "lacks source_chunk_ids" in violations[0]

    def test_06_finding_with_unretrieved_chunk_id_rejected(self):
        chunk = create_sample_chunk()
        unknown_id = uuid.uuid4()
        finding = FinancialFinding(
            metric="revenue",
            period="2025",
            value=1000.0,
            unit="$",
            source_chunk_ids=[unknown_id],
        )

        valid_findings, violations = FinancialFindingValidator.validate_findings(
            findings=[finding],
            retrieved_chunks=[chunk],
        )
        assert len(valid_findings) == 0
        assert len(violations) == 1
        assert "unavailable chunk IDs" in violations[0]

    def test_07_invalid_numeric_and_nan_values_rejected(self):
        chunk = create_sample_chunk()
        finding = FinancialFinding(
            metric="margin",
            period="2025",
            value=float("nan"),
            unit="%",
            source_chunk_ids=[chunk.chunk_id],
        )

        valid_findings, violations = FinancialFindingValidator.validate_findings(
            findings=[finding],
            retrieved_chunks=[chunk],
        )
        assert len(valid_findings) == 0
        assert any("invalid numeric" in v.lower() for v in violations)


class TestCitationValidator:

    def test_08_valid_citations_pass(self):
        chunk = create_sample_chunk()
        cit = create_sample_citation(chunk_id=chunk.chunk_id)
        ans = "Revenue was $1,000. [SOURCE 1]"

        valid_cits, violations = CitationValidator.validate_citations(
            citations=[cit],
            retrieved_chunks=[chunk],
            answer_text=ans,
        )
        assert len(valid_cits) == 1
        assert len(violations) == 0

    def test_09_citation_referencing_unretrieved_chunk_rejected(self):
        chunk = create_sample_chunk()
        unknown_chunk_id = uuid.uuid4()
        cit = create_sample_citation(chunk_id=unknown_chunk_id)
        ans = "Revenue was $1,000. [SOURCE 1]"

        valid_cits, violations = CitationValidator.validate_citations(
            citations=[cit],
            retrieved_chunks=[chunk],
            answer_text=ans,
        )
        assert len(valid_cits) == 0
        assert any("unretrieved chunk" in v for v in violations)

    def test_10_out_of_range_citation_number_flagged(self):
        chunk = create_sample_chunk()
        cit = create_sample_citation(chunk_id=chunk.chunk_id)
        # Text references [SOURCE 5] when only 1 citation exists
        ans = "Revenue was $1,000. [SOURCE 5]"

        valid_cits, violations = CitationValidator.validate_citations(
            citations=[cit],
            retrieved_chunks=[chunk],
            answer_text=ans,
        )
        assert len(violations) == 1
        assert "only 1 valid source citations exist" in violations[0]


class TestGroundingConsistencyValidator:

    def test_11_grounded_true_with_zero_evidence_rejected(self):
        valid, err = GroundingConsistencyValidator.validate_grounding(
            grounded=True,
            retrieved_chunks=[],
            valid_citations=[],
        )
        assert valid is False
        assert "claims grounded=True but no valid retrieved evidence" in err

    def test_12_grounded_true_with_valid_evidence_passes(self):
        chunk = create_sample_chunk()
        cit = create_sample_citation(chunk_id=chunk.chunk_id)

        valid, err = GroundingConsistencyValidator.validate_grounding(
            grounded=True,
            retrieved_chunks=[chunk],
            valid_citations=[cit],
        )
        assert valid is True
        assert err is None


class TestResponseGuardEndToEnd:

    def test_13_complete_valid_financial_research_response_passes(self):
        chunk = create_sample_chunk()
        cit = create_sample_citation(chunk_id=chunk.chunk_id)
        finding = FinancialFinding(
            metric="revenue",
            period="2025",
            value=1000.0,
            unit="$",
            source_chunk_ids=[chunk.chunk_id],
        )

        res = ResponseGuard.validate_output(
            answer="In 2025, total revenue was $1,000 million. [SOURCE 1]",
            citations=[cit],
            retrieved_chunks=[chunk],
            findings=[finding],
            grounded=True,
        )

        assert res.passed is True
        assert res.grounded is True
        assert len(res.validated_citations) == 1
        assert len(res.validated_findings) == 1
        assert "[SOURCE 1]" in res.validated_answer

    def test_14_empty_answer_fails_safely_to_insufficient_evidence(self):
        chunk = create_sample_chunk()
        res = ResponseGuard.validate_output(
            answer="",
            citations=[],
            retrieved_chunks=[chunk],
            findings=[],
            grounded=False,
        )

        assert res.passed is False
        assert res.grounded is False
        assert res.validated_answer == INSUFFICIENT_EVIDENCE_ANSWER
        assert len(res.violation_reasons) >= 1
