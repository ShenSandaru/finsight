"""Planner Agent Node for FinSight Multi-Agent Research System (Sprint 9.1)."""

import logging
import re
from typing import Any

from app.agents.state import ResearchState, PlannerOutput
from app.core.config import get_settings

logger = logging.getLogger("finsight.agents.planner")
settings = get_settings()


class PlannerNode:
    """
    Decomposes complex financial research queries into bounded retrieval sub-questions.
    Deterministic rule-based and entity-driven decomposition avoids unnecessary LLM calls.
    """

    @classmethod
    async def plan(cls, state: ResearchState) -> dict[str, Any]:
        """
        Execute query decomposition:
        - If query is a single-period or simple lookup -> 1 focused subquery.
        - If query asks for comparison across multiple years/periods -> separate subqueries per period.
        - Bounded by settings.AGENT_MAX_SUBQUERIES.
        """
        query = state.get("standalone_query") or state.get("original_query", "")
        clean_q = query.strip()
        logger.info("Planner Node starting for query: '%s'", clean_q[:80])

        # Step 1: Detect multiple fiscal years/periods (e.g., '2024 and 2025', 'Q1 vs Q2')
        years = re.findall(r"\b(20\d\d|19\d\d)\b", clean_q)
        quarters = re.findall(r"\b(Q[1-4])\b", clean_q, flags=re.IGNORECASE)
        periods = list(dict.fromkeys(years + quarters))

        sub_queries: list[str] = []

        if len(periods) >= 2:
            # Strip periods from base query to extract metrics/entities
            base_terms = clean_q
            for p in periods:
                base_terms = re.sub(r"\b" + re.escape(p) + r"\b", "", base_terms, flags=re.IGNORECASE)
            base_terms = re.sub(r"\b(and|vs|versus|compared?|between)\b", " ", base_terms, flags=re.IGNORECASE)
            base_terms = re.sub(r"[?.,!]", "", base_terms)
            base_terms = re.sub(r"\s+", " ", base_terms).strip()

            for p in periods[:settings.AGENT_MAX_SUBQUERIES]:
                sub_queries.append(f"{base_terms} {p}".strip())
        else:
            # Simple question or single-period inquiry
            sub_queries.append(clean_q)

        # Enforce maximum subquery limit and non-empty guarantees
        bounded_queries = [sq for sq in sub_queries if sq.strip()][:settings.AGENT_MAX_SUBQUERIES]
        if not bounded_queries:
            bounded_queries = [clean_q]

        logger.info("Planner Node generated %d sub-queries: %s", len(bounded_queries), bounded_queries)

        return {
            "sub_queries": bounded_queries,
            "step_count": state.get("step_count", 0) + 1,
            "status": "planned",
        }
