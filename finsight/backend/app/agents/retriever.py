"""Retriever Agent Node for FinSight Multi-Agent Research System (Sprint 9.1)."""

import logging
from typing import Any
from uuid import UUID

from app.agents.state import ResearchState
from app.services.retrieval_service import RetrievalService, RetrievalResult

logger = logging.getLogger("finsight.agents.retriever")


class RetrieverNode:
    """
    Executes vector searches for each planner sub-query by calling the existing RetrievalService.search().
    Deduplicates overlapping chunk results across subqueries while preserving highest similarity scores.
    """

    def __init__(self, retrieval_service: RetrievalService | None = None):
        self.retrieval_service = retrieval_service or RetrievalService()

    async def retrieve(self, state: ResearchState) -> dict[str, Any]:
        """
        Execute multi-query retrieval and deduplication.
        """
        sub_queries = state.get("sub_queries") or [state.get("standalone_query", "")]
        top_k = state.get("top_k", 5)
        min_similarity = state.get("min_similarity", 0.0)
        document_id = state.get("document_id")

        logger.info("Retriever Node executing %d sub-queries (top_k=%d, min_sim=%.2f)", len(sub_queries), top_k, min_similarity)

        all_results: list[RetrievalResult] = []
        chunk_map: dict[UUID, RetrievalResult] = {}

        for sq in sub_queries:
            results = await self.retrieval_service.search(
                query=sq,
                top_k=top_k,
                min_similarity=min_similarity,
                document_id=document_id,
            )
            for r in results:
                # Deduplication: if already retrieved by a previous subquery, keep highest similarity
                if r.chunk_id not in chunk_map or r.similarity > chunk_map[r.chunk_id].similarity:
                    chunk_map[r.chunk_id] = r

        # Sort deduplicated chunks by similarity descending
        deduplicated = sorted(chunk_map.values(), key=lambda x: x.similarity, reverse=True)
        logger.info("Retriever Node collected %d unique chunks across %d queries", len(deduplicated), len(sub_queries))

        return {
            "retrieved_chunks": deduplicated,
            "step_count": state.get("step_count", 0) + 1,
            "status": "retrieved",
        }
