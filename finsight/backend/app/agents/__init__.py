"""Multi-Agent Financial Research System Package (Sprint 9.1)."""

from app.agents.state import (
    ResearchState,
    PlannerOutput,
    FinancialFinding,
    FinancialAnalysis,
    AuditedFinding,
    CitationAuditResult,
)
from app.agents.planner import PlannerNode
from app.agents.retriever import RetrieverNode
from app.agents.financial_analyzer import FinancialAnalyzerNode
from app.agents.citation_auditor import CitationAuditorNode
from app.agents.synthesis import SynthesisNode
from app.agents.graph import build_research_graph, FinancialResearchService

__all__ = [
    "ResearchState",
    "PlannerOutput",
    "FinancialFinding",
    "FinancialAnalysis",
    "AuditedFinding",
    "CitationAuditResult",
    "PlannerNode",
    "RetrieverNode",
    "FinancialAnalyzerNode",
    "CitationAuditorNode",
    "SynthesisNode",
    "build_research_graph",
    "FinancialResearchService",
]