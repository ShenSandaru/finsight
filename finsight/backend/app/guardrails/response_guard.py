"""Response Guard Layer for FinSight AI Output Validation (Sprint 9.2)."""

import logging
from typing import Any

from app.core.config import get_settings
from app.services.retrieval_service import RetrievalResult
from app.services.rag_service import (
    SourceCitation,
    validate_and_clean_citations,
    INSUFFICIENT_EVIDENCE_ANSWER,
)
from app.agents.state import FinancialFinding, CitationAuditResult
from app.guardrails.schemas import GuardrailsValidationResult
from app.guardrails.validators import (
    StructureValidator,
    FinancialFindingValidator,
    CitationValidator,
    GroundingConsistencyValidator,
)

logger = logging.getLogger("finsight.guardrails.response_guard")
settings = get_settings()


class ResponseGuard:
    """
    Validates AI-generated responses before they are returned to users or saved to session memory.
    Ensures structural integrity, numerical bounds, citation provenance, and grounding guarantees.
    """

    @classmethod
    def validate_output(
        cls,
        answer: str | None,
        citations: list[SourceCitation],
        retrieved_chunks: list[RetrievalResult],
        findings: list[FinancialFinding] | None = None,
        citation_audit: CitationAuditResult | None = None,
        grounded: bool = True,
    ) -> GuardrailsValidationResult:
        """
        Execute deterministic output guards:
        1. Structure & non-emptiness validation.
        2. Financial findings validation against chunk records.
        3. Citation integrity & chunk presence check.
        4. Citation cleaning / stripping invalid markers.
        5. Grounding consistency validation.
        """
        if not settings.GUARDRAILS_ENABLED:
            logger.info("Guardrails validation is disabled via settings")
            return GuardrailsValidationResult(
                passed=True,
                validated_answer=answer or "",
                validated_citations=citations,
                validated_findings=findings or [],
                grounded=grounded,
                violation_reasons=[],
            )

        all_violations: list[str] = []

        # 1. Structure Check
        struct_valid, clean_ans, struct_err = StructureValidator.validate_answer(answer)
        if not struct_valid:
            logger.warning("Guardrails structure validation failed: %s", struct_err)
            return GuardrailsValidationResult(
                passed=False,
                validated_answer=INSUFFICIENT_EVIDENCE_ANSWER,
                validated_citations=[],
                validated_findings=[],
                grounded=False,
                violation_reasons=[struct_err or "Invalid answer structure"],
            )

        # 2. Financial Findings Validation
        raw_findings = findings or []
        valid_findings, finding_violations = FinancialFindingValidator.validate_findings(
            findings=raw_findings,
            retrieved_chunks=retrieved_chunks,
        )
        if finding_violations:
            all_violations.extend(finding_violations)
            logger.warning("Guardrails rejected %d invalid financial findings", len(finding_violations))

        # 3. Citation Validation & Cleaning
        valid_citations, cit_violations = CitationValidator.validate_citations(
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            answer_text=clean_ans,
        )
        if cit_violations:
            all_violations.extend(cit_violations)
            # Re-clean answer citations to eliminate out-of-range references
            clean_ans = validate_and_clean_citations(clean_ans, len(valid_citations))

        # 4. Grounding Consistency
        ground_valid, ground_err = GroundingConsistencyValidator.validate_grounding(
            grounded=grounded,
            retrieved_chunks=retrieved_chunks,
            valid_citations=valid_citations,
        )
        if not ground_valid:
            all_violations.append(ground_err or "Grounding inconsistency")
            logger.warning("Guardrails grounding consistency failed: %s", ground_err)
            return GuardrailsValidationResult(
                passed=False,
                validated_answer=INSUFFICIENT_EVIDENCE_ANSWER,
                validated_citations=[],
                validated_findings=[],
                grounded=False,
                violation_reasons=all_violations,
            )

        # 5. Determine Final Passed Status
        passed = len(all_violations) == 0 or (len(valid_citations) > 0 and len(clean_ans) > 0)
        final_grounded = grounded and len(valid_citations) > 0 and len(retrieved_chunks) > 0

        logger.info(
            "Guardrails Output Validation finished: passed=%s (grounded=%s, citations=%d, findings=%d, violations=%d)",
            passed,
            final_grounded,
            len(valid_citations),
            len(valid_findings),
            len(all_violations),
        )

        return GuardrailsValidationResult(
            passed=passed,
            validated_answer=clean_ans,
            validated_citations=valid_citations,
            validated_findings=valid_findings,
            grounded=final_grounded,
            violation_reasons=all_violations,
        )
