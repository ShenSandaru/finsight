"""Grounded RAG Context Assembly & Answer Generation Service (Sprint 7.1)."""

import re
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.services.retrieval_service import RetrievalService, RetrievalResult
from app.services.generation_service import GenerationService

logger = logging.getLogger("finsight.services.rag")
settings = get_settings()

INSUFFICIENT_EVIDENCE_ANSWER = "I could not find enough relevant information in the indexed documents to answer this question."


@dataclass
class SourceCitation:
    """Structured data contract for an individual source citation backing a RAG answer."""
    chunk_id: UUID
    document_id: UUID
    page_number: int | None
    chunk_type: str
    similarity: float
    statement_type: str | None
    fiscal_periods: list[str]


@dataclass
class RAGResponse:
    """Structured data contract for the complete RAG answer output."""
    query: str
    answer: str
    citations: list[SourceCitation]
    retrieved_chunks: int
    grounded: bool


def build_context(
    results: list[RetrievalResult],
    max_chars: int = settings.RAG_MAX_CONTEXT_CHARS,
) -> tuple[str, list[SourceCitation]]:
    """
    Assemble ranked retrieval results into a structured evidence context string with [SOURCE N] markers.
    Strictly preserves retrieval order and page metadata while enforcing the max character budget.
    Never splits a chunk mid-way.
    """
    if not results:
        return "", []

    context_blocks: list[str] = []
    citations: list[SourceCitation] = []
    current_char_count = 0

    for idx, r in enumerate(results):
        source_num = idx + 1
        meta = r.metadata if isinstance(r.metadata, dict) else {}
        statement_type = meta.get("statement_type")
        fiscal_periods = meta.get("fiscal_periods", [])
        if not isinstance(fiscal_periods, list):
            fiscal_periods = [str(fiscal_periods)] if fiscal_periods else []
        currency = meta.get("currency")
        units = meta.get("units")

        header_lines = [
            f"[SOURCE {source_num}]",
            f"Document ID: {r.document_id}",
            f"Chunk ID: {r.chunk_id}",
            f"Page: {r.page_number if r.page_number is not None else 'Unknown'}",
            f"Chunk Type: {r.chunk_type}",
            f"Similarity: {r.similarity:.4f}",
        ]
        if statement_type:
            header_lines.append(f"Statement Type: {statement_type}")
        if fiscal_periods:
            header_lines.append(f"Fiscal Periods: {', '.join(str(p) for p in fiscal_periods)}")
        if currency:
            header_lines.append(f"Currency: {currency}")
        if units:
            header_lines.append(f"Units: {units}")

        header_lines.append("\nContent:")
        header_lines.append(r.content.strip())
        block_text = "\n".join(header_lines)

        block_len = len(block_text) + (2 if context_blocks else 0)  # accounting for "\n\n"
        if current_char_count + block_len > max_chars:
            logger.info(
                "Context limit reached (%d + %d > %d chars). Stopping context assembly at %d sources.",
                current_char_count,
                block_len,
                max_chars,
                len(citations),
            )
            break

        context_blocks.append(block_text)
        current_char_count += block_len

        citations.append(
            SourceCitation(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                page_number=r.page_number,
                chunk_type=r.chunk_type,
                similarity=r.similarity,
                statement_type=statement_type,
                fiscal_periods=fiscal_periods,
            )
        )

    full_context = "\n\n".join(context_blocks)
    return full_context, citations


def validate_and_clean_citations(answer: str, num_valid_sources: int) -> str:
    """
    Validate that any [SOURCE N] citations in the answer reference valid source indices (1 <= N <= num_valid_sources).
    Removes unsupported citations to guarantee grounding consistency.
    """
    if num_valid_sources <= 0:
        # If no valid sources, remove any hallucinated [SOURCE N] markers
        return re.sub(r"\[SOURCE\s+\d+\]", "", answer).strip()

    def replace_citation(match: re.Match) -> str:
        marker = match.group(0)
        digits = re.findall(r"\d+", marker)
        if digits:
            num = int(digits[0])
            if 1 <= num <= num_valid_sources:
                return marker
        # Out-of-bounds citation: strip marker
        return ""

    cleaned = re.sub(r"\[SOURCE\s+\d+\]", replace_citation, answer)
    return re.sub(r"\s+", " ", cleaned).strip()


class RAGService:
    """
    Orchestrates Grounded Financial Question Answering (Sprint 7.1).
    Retrieves candidate chunks via RetrievalService, builds structured context, and queries GenerationService.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        generation_service: GenerationService | None = None,
    ):
        self.retrieval_service = retrieval_service or RetrievalService()
        self.generation_service = generation_service or GenerationService()

    async def answer(
        self,
        query: str,
        top_k: int = settings.RAG_DEFAULT_TOP_K,
        min_similarity: float | None = None,
        document_id: UUID | None = None,
        document_ids: list[UUID] | None = None,
        db: AsyncSession | None = None,
    ) -> RAGResponse:
        """
        Execute end-to-end grounded RAG answering for a user financial question.
        1. Validates inputs.
        2. Retrieves chunks via RetrievalService.
        3. Checks relevance threshold (short-circuits if insufficient evidence).
        4. Assembles evidence context bounded by character limit.
        5. Calls GenerationService with grounding instructions.
        6. Validates source citations and returns RAGResponse.
        """
        # Step 1: Input Validation
        if not isinstance(query, str) or not query.strip():
            raise ValidationError(
                message="Query must be a non-empty string",
                details={"query": query},
            )

        if not isinstance(top_k, int) or top_k < 1 or top_k > settings.RAG_MAX_TOP_K:
            raise ValidationError(
                message=f"top_k must be an integer between 1 and {settings.RAG_MAX_TOP_K}",
                details={"top_k": top_k, "max_allowed": settings.RAG_MAX_TOP_K},
            )

        threshold = min_similarity if min_similarity is not None else settings.RAG_MIN_RELEVANCE_SCORE
        if not isinstance(threshold, (int, float)) or threshold < 0.0 or threshold > 1.0:
            raise ValidationError(
                message="min_similarity must be a float between 0.0 and 1.0",
                details={"min_similarity": threshold},
            )

        # Step 2: Retrieve Indexed Chunks via RetrievalService
        results = await self.retrieval_service.search(
            query=query.strip(),
            top_k=top_k,
            min_similarity=threshold,
            document_id=document_id,
            document_ids=document_ids,
            db=db,
        )

        # Step 3: Insufficient Evidence Short-Circuit (Zero LLM calls)
        if not results:
            logger.info("No chunks met similarity threshold %.2f for query '%s'. Short-circuiting RAG.", threshold, query[:50])
            return RAGResponse(
                query=query.strip(),
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                citations=[],
                retrieved_chunks=0,
                grounded=False,
            )

        # Step 4: Context Assembly
        context_str, citations = build_context(results, max_chars=settings.RAG_MAX_CONTEXT_CHARS)
        if not context_str or not citations:
            return RAGResponse(
                query=query.strip(),
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                citations=[],
                retrieved_chunks=0,
                grounded=False,
            )

        # Step 5: Grounded Answer Generation
        raw_answer = await self.generation_service.generate_answer(
            query=query.strip(),
            context=context_str,
        )

        # Step 6: Validate Citations in Answer
        cleaned_answer = validate_and_clean_citations(raw_answer, len(citations))

        return RAGResponse(
            query=query.strip(),
            answer=cleaned_answer,
            citations=citations,
            retrieved_chunks=len(citations),
            grounded=True,
        )
