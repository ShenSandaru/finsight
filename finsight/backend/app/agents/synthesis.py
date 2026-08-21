"""Synthesis Agent Node for FinSight Multi-Agent Research System (Sprint 9.1)."""

import logging
from typing import Any

from app.agents.state import ResearchState
from app.services.generation_service import GenerationService
from app.services.rag_service import (
    build_context,
    validate_and_clean_citations,
    INSUFFICIENT_EVIDENCE_ANSWER,
    SourceCitation,
)

logger = logging.getLogger("finsight.agents.synthesis")


class SynthesisNode:
    """
    Synthesizes the final grounded financial research answer using the verified findings,
    retrieved evidence context, and GenerationService. Reuses existing citation infrastructure.
    """

    def __init__(self, generation_service: GenerationService | None = None):
        self.generation_service = generation_service or GenerationService()

    async def synthesize(self, state: ResearchState) -> dict[str, Any]:
        """
        Execute grounded synthesis combining retrieved chunks and audited findings.
        """
        chunks = state.get("retrieved_chunks", [])
        findings = state.get("findings", [])
        audit = state.get("citation_audit")
        query = state.get("original_query", "")

        # 1. Check for insufficient evidence
        if not chunks or (audit and not audit.passed and not findings):
            logger.info("Insufficient evidence in research state. Short-circuiting synthesis.")
            return {
                "final_answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "citations": [],
                "grounded": False,
                "step_count": state.get("step_count", 0) + 1,
                "status": "completed_no_evidence",
            }

        # 2. Build structured context from retrieved chunks
        context_str, citations = build_context(chunks)

        # 3. Add audited financial findings summary to context if available
        if audit and audit.audited_findings:
            findings_lines = ["\n[AUDITED FINANCIAL FINDINGS]"]
            for f in audit.audited_findings:
                findings_lines.append(f"- {f.metric.replace('_', ' ').title()} ({f.period}): {f.value} {f.audit_notes}")
            context_str += "\n" + "\n".join(findings_lines)

        # 4. Generate answer via GenerationService
        logger.info("Synthesis Node generating final grounded research answer for query '%s'", query[:60])
        raw_answer = await self.generation_service.generate_answer(
            query=query,
            context=context_str,
        )

        # 5. Clean & validate source citations
        cleaned_answer = validate_and_clean_citations(raw_answer, len(citations))

        return {
            "final_answer": cleaned_answer,
            "citations": citations,
            "grounded": True,
            "step_count": state.get("step_count", 0) + 1,
            "status": "completed",
        }
