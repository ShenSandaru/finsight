"""LangGraph Orchestration for Multi-Agent Financial Research Workflow (Sprint 9.1)."""

import logging
from typing import Any
from uuid import UUID

from langgraph.graph import StateGraph, START, END

from app.agents.state import ResearchState
from app.agents.planner import PlannerNode
from app.agents.retriever import RetrieverNode
from app.agents.financial_analyzer import FinancialAnalyzerNode
from app.agents.citation_auditor import CitationAuditorNode
from app.agents.synthesis import SynthesisNode
from app.services.retrieval_service import RetrievalService
from app.services.generation_service import GenerationService
from app.services.rag_service import INSUFFICIENT_EVIDENCE_ANSWER

from app.guardrails.response_guard import ResponseGuard

logger = logging.getLogger("finsight.agents.graph")


def route_after_retrieval(state: ResearchState) -> str:
    """
    Conditional routing edge after retrieval:
    - If no chunks were retrieved -> route straight to END (insufficient evidence).
    - If chunks were found -> route to Financial Analyzer node.
    """
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        logger.info("No chunks retrieved. Routing to END with insufficient evidence.")
        return "insufficient_evidence"
    return "financial_analyzer"


def route_after_audit(state: ResearchState) -> str:
    """
    Conditional routing edge after citation audit:
    - If audit passed -> route to Synthesis.
    - If audit failed completely -> route to END.
    """
    audit = state.get("citation_audit")
    if audit and not audit.passed and not state.get("findings"):
        logger.warning("Citation audit failed. Routing to END.")
        return "insufficient_evidence"
    return "synthesis"


async def guardrails_validator_node(state: ResearchState) -> dict[str, Any]:
    """
    Guardrails AI Output Validation Node:
    Executes deterministic structural, finding, citation, and grounding checks on the synthesized response.
    """
    answer = state.get("final_answer")
    citations = state.get("citations", [])
    chunks = state.get("retrieved_chunks", [])
    findings = state.get("findings", [])
    audit = state.get("citation_audit")
    grounded = state.get("grounded", True)

    logger.info("Guardrails Node validating synthesized response (citations=%d, chunks=%d)", len(citations), len(chunks))

    guard_res = ResponseGuard.validate_output(
        answer=answer,
        citations=citations,
        retrieved_chunks=chunks,
        findings=findings,
        citation_audit=audit,
        grounded=grounded,
    )

    return {
        "final_answer": guard_res.validated_answer,
        "citations": guard_res.validated_citations,
        "findings": guard_res.validated_findings,
        "grounded": guard_res.grounded,
        "guardrails_validation": guard_res,
        "step_count": state.get("step_count", 0) + 1,
        "status": "validated" if guard_res.passed else "validation_failed",
    }


async def no_evidence_handler(state: ResearchState) -> dict[str, Any]:
    """Fallback node producing clean insufficient evidence response without LLM calls."""
    return {
        "final_answer": INSUFFICIENT_EVIDENCE_ANSWER,
        "citations": [],
        "grounded": False,
        "step_count": state.get("step_count", 0) + 1,
        "status": "completed_no_evidence",
    }


def build_research_graph(
    retrieval_service: RetrievalService | None = None,
    generation_service: GenerationService | None = None,
):
    """
    Construct the compiled LangGraph StateGraph for multi-agent financial research:
    START -> Planner -> Retriever -> (conditional) -> Analyzer -> Auditor -> (conditional) -> Synthesis -> Guardrails -> END
    """
    retriever_node = RetrieverNode(retrieval_service=retrieval_service)
    synthesis_node = SynthesisNode(generation_service=generation_service)

    workflow = StateGraph(ResearchState)

    # 1. Register Nodes
    workflow.add_node("planner", PlannerNode.plan)
    workflow.add_node("retriever", retriever_node.retrieve)
    workflow.add_node("financial_analyzer", FinancialAnalyzerNode.analyze)
    workflow.add_node("citation_auditor", CitationAuditorNode.audit)
    workflow.add_node("synthesis", synthesis_node.synthesize)
    workflow.add_node("guardrails", guardrails_validator_node)
    workflow.add_node("no_evidence", no_evidence_handler)

    # 2. Register Edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "retriever")

    workflow.add_conditional_edges(
        "retriever",
        route_after_retrieval,
        {
            "financial_analyzer": "financial_analyzer",
            "insufficient_evidence": "no_evidence",
        },
    )

    workflow.add_edge("financial_analyzer", "citation_auditor")

    workflow.add_conditional_edges(
        "citation_auditor",
        route_after_audit,
        {
            "synthesis": "synthesis",
            "insufficient_evidence": "no_evidence",
        },
    )

    workflow.add_edge("synthesis", "guardrails")
    workflow.add_edge("guardrails", END)
    workflow.add_edge("no_evidence", END)

    return workflow.compile()


class FinancialResearchService:
    """
    High-level entry point service orchestrating the multi-agent research graph.
    Can be called synchronously from API routes or background tasks.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        generation_service: GenerationService | None = None,
    ):
        self.retrieval_service = retrieval_service or RetrievalService()
        self.generation_service = generation_service or GenerationService()
        self.graph = build_research_graph(
            retrieval_service=self.retrieval_service,
            generation_service=self.generation_service,
        )

    async def execute_research(
        self,
        query: str,
        standalone_query: str | None = None,
        session_id: UUID | None = None,
        document_id: UUID | None = None,
        top_k: int = 5,
        min_similarity: float = 0.30,
    ) -> ResearchState:
        """
        Execute the multi-agent graph with initial ResearchState.
        """
        initial_state: ResearchState = {
            "session_id": session_id,
            "original_query": query.strip(),
            "standalone_query": standalone_query.strip() if standalone_query else query.strip(),
            "document_id": document_id,
            "top_k": top_k,
            "min_similarity": min_similarity,
            "sub_queries": [],
            "retrieved_chunks": [],
            "findings": [],
            "citation_audit": None,
            "guardrails_validation": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 0,
            "status": "started",
            "error": None,
        }

        logger.info("Executing Financial Research Graph for query '%s'", query[:60])
        final_state = await self.graph.ainvoke(initial_state)
        return final_state
