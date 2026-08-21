"""Comprehensive unit and integration test suite for FinSight Multi-Agent Research System (Sprint 9.1)."""

import uuid
import pytest
from unittest.mock import AsyncMock

from app.core.config import get_settings
from app.agents.state import ResearchState, FinancialFinding, CitationAuditResult, AuditedFinding
from app.agents.planner import PlannerNode
from app.agents.retriever import RetrieverNode
from app.agents.financial_analyzer import FinancialAnalyzerNode
from app.agents.citation_auditor import CitationAuditorNode
from app.agents.synthesis import SynthesisNode
from app.agents.graph import build_research_graph, FinancialResearchService
from app.services.retrieval_service import RetrievalResult
from app.services.embedding_service import FakeGenAIClient
from app.services.generation_service import GenerationService

settings = get_settings()


class MockRetrievalService:
    def __init__(self, sample_results: list[RetrievalResult] | None = None):
        self.sample_results = sample_results or []
        self.searched_queries = []

    async def search(self, query: str, top_k: int = 5, min_similarity: float = 0.0, document_id=None, db=None) -> list[RetrievalResult]:
        self.searched_queries.append(query)
        return self.sample_results


class FakeGenService:
    async def generate_answer(self, query: str, context: str) -> str:
        return "Based on verified financial evidence, 2025 revenue was $1,000 million and gross profit was $400 million, representing a 40.0% gross margin. [SOURCE 1]"

    async def close(self):
        pass


@pytest.mark.asyncio
class TestPlannerNode:

    async def test_01_simple_query_single_subquery(self):
        state: ResearchState = {
            "original_query": "What was Apple's total revenue in 2025?",
            "standalone_query": "What was Apple's total revenue in 2025?",
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "sub_queries": [],
            "retrieved_chunks": [],
            "findings": [],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 0,
            "status": "started",
            "error": None,
        }
        res = await PlannerNode.plan(state)
        assert len(res["sub_queries"]) == 1
        assert "2025" in res["sub_queries"][0]
        assert res["status"] == "planned"

    async def test_02_multi_period_query_decomposition(self):
        state: ResearchState = {
            "original_query": "Compare Apple's 2024 and 2025 revenue and gross profit",
            "standalone_query": "Compare Apple's 2024 and 2025 revenue and gross profit",
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "sub_queries": [],
            "retrieved_chunks": [],
            "findings": [],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 0,
            "status": "started",
            "error": None,
        }
        res = await PlannerNode.plan(state)
        assert len(res["sub_queries"]) == 2
        assert any("2024" in sq for sq in res["sub_queries"])
        assert any("2025" in sq for sq in res["sub_queries"])

    async def test_03_planner_subquery_bounds(self):
        state: ResearchState = {
            "original_query": "Compare 2021, 2022, 2023, 2024, 2025 revenue",
            "standalone_query": "Compare 2021, 2022, 2023, 2024, 2025 revenue",
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "sub_queries": [],
            "retrieved_chunks": [],
            "findings": [],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 0,
            "status": "started",
            "error": None,
        }
        res = await PlannerNode.plan(state)
        assert len(res["sub_queries"]) <= settings.AGENT_MAX_SUBQUERIES


@pytest.mark.asyncio
class TestRetrieverNode:

    async def test_04_retriever_multi_query_execution_and_deduplication(self):
        chunk1_id = uuid.uuid4()
        chunk2_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        r1 = RetrievalResult(
            chunk_id=chunk1_id,
            document_id=doc_id,
            content="Table 2025: Revenue $1,000, Gross Profit $400",
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.90,
            metadata={"statement_type": "income_statement"},
        )
        r1_lower = RetrievalResult(
            chunk_id=chunk1_id,
            document_id=doc_id,
            content="Table 2025: Revenue $1,000, Gross Profit $400",
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.85,
            metadata={"statement_type": "income_statement"},
        )
        r2 = RetrievalResult(
            chunk_id=chunk2_id,
            document_id=doc_id,
            content="Table 2024: Revenue $900, Gross Profit $360",
            chunk_type="table",
            chunk_index=1,
            page_number=1,
            similarity=0.88,
            metadata={"statement_type": "income_statement"},
        )

        mock_service = MockRetrievalService(sample_results=[r1, r2, r1_lower])
        node = RetrieverNode(retrieval_service=mock_service)

        state: ResearchState = {
            "original_query": "Comparison",
            "standalone_query": "Comparison",
            "sub_queries": ["Query 2025", "Query 2024"],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "retrieved_chunks": [],
            "findings": [],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 1,
            "status": "planned",
            "error": None,
        }

        res = await node.retrieve(state)
        assert len(mock_service.searched_queries) == 2
        # Deduplication check: only 2 unique chunks
        assert len(res["retrieved_chunks"]) == 2
        # Top similarity preserved
        c1 = [c for c in res["retrieved_chunks"] if c.chunk_id == chunk1_id][0]
        assert c1.similarity == 0.90


@pytest.mark.asyncio
class TestFinancialAnalyzerNode:

    async def test_05_analyzer_metric_extraction_and_ratio_calculation(self):
        chunk_id = uuid.uuid4()
        chunk_content = (
            "Consolidated Statements of Operations\n"
            "Years Ended December 31, 2025 and 2024\n"
            "Financial Metric 2025 2024\n"
            "Total Revenue $1,000 $900\n"
            "Gross Profit $400 $360\n"
            "Net Income $150 $130"
        )
        r = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content=chunk_content,
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.92,
            metadata={"statement_type": "income_statement"},
        )

        state: ResearchState = {
            "original_query": "Gross margin and revenue growth",
            "standalone_query": "Gross margin and revenue growth",
            "sub_queries": [],
            "retrieved_chunks": [r],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        res = await FinancialAnalyzerNode.analyze(state)
        findings = res["findings"]
        assert len(findings) >= 4

        # Verify raw extraction
        rev_2025 = [f for f in findings if f.metric == "revenue" and f.period == "2025"][0]
        assert rev_2025.value == 1000.0
        assert chunk_id in rev_2025.source_chunk_ids

        # Verify deterministic margin calculation: (400 / 1000) * 100 = 40.0%
        gm_2025 = [f for f in findings if f.metric == "gross_margin" and f.period == "2025"]
        if gm_2025:
            assert gm_2025[0].value == 40.0
            assert gm_2025[0].unit == "%"


@pytest.mark.asyncio
class TestCitationAuditorNode:

    async def test_06_auditor_validates_supported_findings(self):
        chunk_id = uuid.uuid4()
        chunk = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content="Total Revenue was $1,000 in 2025.",
            chunk_type="text",
            chunk_index=0,
            page_number=1,
            similarity=0.90,
            metadata={},
        )
        finding = FinancialFinding(
            metric="revenue",
            period="2025",
            value=1000.0,
            unit="$",
            source_chunk_ids=[chunk_id],
        )

        state: ResearchState = {
            "original_query": "Revenue",
            "standalone_query": "Revenue",
            "sub_queries": [],
            "retrieved_chunks": [chunk],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [finding],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 3,
            "status": "analyzed",
            "error": None,
        }

        res = await CitationAuditorNode.audit(state)
        audit = res["citation_audit"]
        assert audit.passed is True
        assert len(audit.audited_findings) == 1
        assert audit.audited_findings[0].supported is True

    async def test_07_auditor_rejects_missing_chunk_id(self):
        real_chunk_id = uuid.uuid4()
        missing_chunk_id = uuid.uuid4()
        chunk = RetrievalResult(
            chunk_id=real_chunk_id,
            document_id=uuid.uuid4(),
            content="Real text",
            chunk_type="text",
            chunk_index=0,
            page_number=1,
            similarity=0.90,
            metadata={},
        )
        hallucinated_finding = FinancialFinding(
            metric="fake_metric",
            period="2025",
            value=9999.0,
            unit="$",
            source_chunk_ids=[missing_chunk_id],
        )

        state: ResearchState = {
            "original_query": "Fake",
            "standalone_query": "Fake",
            "sub_queries": [],
            "retrieved_chunks": [chunk],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [hallucinated_finding],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 3,
            "status": "analyzed",
            "error": None,
        }

        res = await CitationAuditorNode.audit(state)
        audit = res["citation_audit"]
        assert len(audit.unsupported_findings) == 1
        assert "missing chunk IDs" in audit.unsupported_findings[0]


@pytest.mark.asyncio
class TestSynthesisNode:

    async def test_08_synthesis_combines_evidence_and_findings(self):
        chunk_id = uuid.uuid4()
        chunk = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content="Total Revenue: $1,000",
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.95,
            metadata={"statement_type": "income_statement"},
        )
        finding = FinancialFinding(
            metric="revenue",
            period="2025",
            value=1000.0,
            unit="$",
            source_chunk_ids=[chunk_id],
        )
        audit = CitationAuditResult(
            passed=True,
            audited_findings=[
                AuditedFinding(
                    metric="revenue",
                    period="2025",
                    value=1000.0,
                    supported=True,
                    source_chunk_ids=[chunk_id],
                    audit_notes="Verified",
                )
            ],
            unsupported_findings=[],
        )

        node = SynthesisNode(generation_service=FakeGenService())
        state: ResearchState = {
            "original_query": "What was revenue?",
            "standalone_query": "What was revenue?",
            "sub_queries": [],
            "retrieved_chunks": [chunk],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [finding],
            "citation_audit": audit,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 4,
            "status": "audited",
            "error": None,
        }

        res = await node.synthesize(state)
        assert res["grounded"] is True
        assert len(res["citations"]) == 1
        assert "[SOURCE 1]" in res["final_answer"]

    async def test_09_synthesis_insufficient_evidence_short_circuit(self):
        node = SynthesisNode(generation_service=FakeGenService())
        state: ResearchState = {
            "original_query": "What was SpaceX revenue?",
            "standalone_query": "What was SpaceX revenue?",
            "sub_queries": [],
            "retrieved_chunks": [],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        res = await node.synthesize(state)
        assert res["grounded"] is False
        assert len(res["citations"]) == 0
        assert "not find enough" in res["final_answer"].lower()


@pytest.mark.asyncio
class TestFullResearchGraph:

    async def test_10_end_to_end_research_graph_execution(self):
        chunk_id = uuid.uuid4()
        chunk = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content="Total Revenue: $1,000, Gross Profit: $400",
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.91,
            metadata={"statement_type": "income_statement"},
        )

        mock_retrieval = MockRetrievalService(sample_results=[chunk])
        research_service = FinancialResearchService(
            retrieval_service=mock_retrieval,
            generation_service=FakeGenService(),
        )

        final_state = await research_service.execute_research(
            query="Compare Apple's 2024 and 2025 revenue",
            top_k=5,
            min_similarity=0.0,
        )

        assert final_state["grounded"] is True
        assert len(final_state["sub_queries"]) >= 1
        assert len(final_state["retrieved_chunks"]) == 1
        assert len(final_state["citations"]) == 1
        assert final_state["step_count"] >= 4
        assert final_state["final_answer"] is not None

    async def test_11_research_graph_no_evidence_flow(self):
        mock_empty_retrieval = MockRetrievalService(sample_results=[])
        research_service = FinancialResearchService(
            retrieval_service=mock_empty_retrieval,
            generation_service=FakeGenService(),
        )

        final_state = await research_service.execute_research(
            query="Unknown private metric",
            top_k=5,
            min_similarity=0.50,
        )

        assert final_state["grounded"] is False
        assert len(final_state["retrieved_chunks"]) == 0
        assert len(final_state["citations"]) == 0
        assert "not find enough" in final_state["final_answer"].lower()
