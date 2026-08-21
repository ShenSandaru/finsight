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

    async def test_05b_extended_financial_metrics_calculations(self):
        """Sprint 10.1: Test Operating Margin, ROA, Current Ratio, Debt-to-Equity, and Free Cash Flow."""
        chunk_id = uuid.uuid4()
        chunk_content = (
            "Consolidated Financial Statements\n"
            "Year Ended December 31, 2025\n"
            "Total Revenue: $1,000\n"
            "Operating Income: $300\n"
            "Net Income: $150\n"
            "Total Current Assets: $600\n"
            "Total Current Liabilities: $300\n"
            "Total Assets: $1,500\n"
            "Total Liabilities: $600\n"
            "Total Stockholders' Equity: $900\n"
            "Operating Cash Flow: $400\n"
            "Capital Expenditures: $150"
        )
        r = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content=chunk_content,
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.95,
            metadata={"statement_type": "income_statement"},
        )

        state: ResearchState = {
            "original_query": "Calculate all financial ratios for 2025",
            "standalone_query": "Calculate all financial ratios for 2025",
            "sub_queries": [],
            "retrieved_chunks": [r],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "guardrails_validation": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        res = await FinancialAnalyzerNode.analyze(state)
        findings = res["findings"]

        # 1. Operating Margin: (300 / 1000) * 100 = 30.0%
        op_margin = [f for f in findings if f.metric == "operating_margin" and f.period == "2025"][0]
        assert op_margin.value == 30.0
        assert op_margin.unit == "%"
        assert chunk_id in op_margin.source_chunk_ids

        # 2. Return on Assets (ROA): (150 / 1500) * 100 = 10.0%
        roa = [f for f in findings if f.metric == "roa" and f.period == "2025"][0]
        assert roa.value == 10.0
        assert roa.unit == "%"
        assert chunk_id in roa.source_chunk_ids

        # 3. Current Ratio: 600 / 300 = 2.0
        cr = [f for f in findings if f.metric == "current_ratio" and f.period == "2025"][0]
        assert cr.value == 2.0
        assert cr.unit == "ratio"

        # 4. Debt-to-Equity: 600 / 900 = 0.67
        dte = [f for f in findings if f.metric == "debt_to_equity" and f.period == "2025"][0]
        assert dte.value == 0.67
        assert dte.unit == "ratio"

        # 5. Free Cash Flow (FCF): 400 - 150 = 250.0
        fcf = [f for f in findings if f.metric == "free_cash_flow" and f.period == "2025"][0]
        assert fcf.value == 250.0
        assert fcf.unit == "$"

    async def test_05c_edge_cases_zero_division_and_negative_values(self):
        """Sprint 10.1: Test zero division safety, missing denominator, and negative net income."""
        chunk_id = uuid.uuid4()
        chunk_content = (
            "Consolidated Statements of Operations\n"
            "Year Ended December 31, 2025\n"
            "Total Revenue: $0\n"
            "Operating Income: $(100)\n"
            "Net Income: $(50)\n"
            "Total Assets: $0\n"
            "Total Liabilities: $300\n"
            "Total Stockholders' Equity: $0\n"
            "Operating Cash Flow: $(80)\n"
            "Capital Expenditures: $(40)"
        )
        r = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content=chunk_content,
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.90,
            metadata={},
        )

        state: ResearchState = {
            "original_query": "Calculate ratios",
            "standalone_query": "Calculate ratios",
            "sub_queries": [],
            "retrieved_chunks": [r],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "guardrails_validation": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        # Should complete gracefully without ZeroDivisionError or crash
        res = await FinancialAnalyzerNode.analyze(state)
        findings = res["findings"]

        # Revenue = 0 -> Operating Margin & ROA (Assets = 0) & D/E (Equity = 0) skipped safely
        assert not any(f.metric == "operating_margin" for f in findings)
        assert not any(f.metric == "roa" for f in findings)
        assert not any(f.metric == "debt_to_equity" for f in findings)

        # FCF with negative OCF (-80) and negative/bracketed CapEx (-40): -80 - 40 = -120.0
        fcf = [f for f in findings if f.metric == "free_cash_flow"][0]
        assert fcf.value == -120.0

    async def test_05d_multi_period_cagr_and_sequential_yoy(self):
        """Sprint 10.2: Test chronological ordering, sequential YoY across 4 years, and CAGR."""
        chunk1_id = uuid.uuid4()
        chunk2_id = uuid.uuid4()

        # Input text arrives with unordered years: 2025, 2022, 2024, 2023
        chunk1 = RetrievalResult(
            chunk_id=chunk1_id,
            document_id=uuid.uuid4(),
            content=(
                "Historical Revenue Operations\n"
                "Years 2025 2022\n"
                "Total Revenue $150 $100"
            ),
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.92,
            metadata={},
        )
        chunk2 = RetrievalResult(
            chunk_id=chunk2_id,
            document_id=uuid.uuid4(),
            content=(
                "Historical Revenue Operations\n"
                "Years 2024 2023\n"
                "Total Revenue $135 $115"
            ),
            chunk_type="table",
            chunk_index=1,
            page_number=2,
            similarity=0.91,
            metadata={},
        )

        state: ResearchState = {
            "original_query": "Revenue trend and CAGR from 2022 to 2025",
            "standalone_query": "Revenue trend and CAGR from 2022 to 2025",
            "sub_queries": [],
            "retrieved_chunks": [chunk1, chunk2],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "guardrails_validation": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        res = await FinancialAnalyzerNode.analyze(state)
        findings = res["findings"]

        # 1. Sequential YoY checks
        # 2022 = 100, 2023 = 115 => 2023 vs 2022 = +15.0%
        yoy_23_22 = [f for f in findings if f.metric == "revenue_growth" and f.period == "2023_vs_2022"][0]
        assert yoy_23_22.value == 15.0

        # 2023 = 115, 2024 = 135 => 2024 vs 2023 = +17.39%
        yoy_24_23 = [f for f in findings if f.metric == "revenue_growth" and f.period == "2024_vs_2023"][0]
        assert yoy_24_23.value == 17.39

        # 2024 = 135, 2025 = 150 => 2025 vs 2024 = +11.11%
        yoy_25_24 = [f for f in findings if f.metric == "revenue_growth" and f.period == "2025_vs_2024"][0]
        assert yoy_25_24.value == 11.11

        # 2. Multi-year CAGR: 2022 ($100) to 2025 ($150) over N = 3 elapsed years
        # ((150 / 100) ^ (1/3) - 1) * 100 = 14.47%
        cagr = [f for f in findings if f.metric == "revenue_cagr" and f.period == "2022_to_2025"][0]
        assert cagr.value == 14.47
        assert cagr.unit == "%"
        # Provenance must merge all source chunk IDs
        assert chunk1_id in cagr.source_chunk_ids
        assert chunk2_id in cagr.source_chunk_ids

        # 3. Deterministic Trend: 100 -> 115 -> 135 -> 150 => Consistent Increase
        trend = [f for f in findings if f.metric == "revenue_trend" and f.period == "2022_to_2025"][0]
        assert trend.unit == "trend"
        assert "Consistent Increase" in trend.calculation

    async def test_05e_cagr_missing_intermediate_years_and_edge_cases(self):
        """Sprint 10.2: Test CAGR elapsed years with missing intermediate periods, volatile trends, and negative start."""
        chunk_id = uuid.uuid4()
        # 2020 = 100, 2025 = 150 (missing 2021, 2022, 2023, 2024) -> N = 5 elapsed years
        # ((150 / 100) ^ (1/5) - 1) * 100 = 8.45%
        chunk = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content=(
                "Financial Growth Summary\n"
                "Years 2025 2020\n"
                "Total Revenue $150 $100"
            ),
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.95,
            metadata={},
        )

        state: ResearchState = {
            "original_query": "Revenue CAGR from 2020 to 2025",
            "standalone_query": "Revenue CAGR from 2020 to 2025",
            "sub_queries": [],
            "retrieved_chunks": [chunk],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "guardrails_validation": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        res = await FinancialAnalyzerNode.analyze(state)
        findings = res["findings"]

        cagr = [f for f in findings if f.metric == "revenue_cagr" and f.period == "2020_to_2025"][0]
        assert cagr.value == 8.45
        assert "Incomplete Series" in cagr.calculation

    async def test_05f_trend_classifications_decrease_flat_volatile(self):
        """Sprint 10.2: Test Consistent Decrease, Flat, and Volatile trend classifications."""
        chunk_id = uuid.uuid4()
        chunk = RetrievalResult(
            chunk_id=chunk_id,
            document_id=uuid.uuid4(),
            content=(
                "Multi-Year Income Statements\n"
                "Years 2025 2024 2023\n"
                "Total Revenue $100 $100 $100\n"
                "Operating Income $100 $120 $90\n"
                "Gross Profit $80 $90 $100"
            ),
            chunk_type="table",
            chunk_index=0,
            page_number=1,
            similarity=0.95,
            metadata={},
        )

        state: ResearchState = {
            "original_query": "Multi-year trends",
            "standalone_query": "Multi-year trends",
            "sub_queries": [],
            "retrieved_chunks": [chunk],
            "session_id": None,
            "document_id": None,
            "top_k": 5,
            "min_similarity": 0.0,
            "findings": [],
            "citation_audit": None,
            "guardrails_validation": None,
            "final_answer": None,
            "citations": [],
            "grounded": False,
            "step_count": 2,
            "status": "retrieved",
            "error": None,
        }

        res = await FinancialAnalyzerNode.analyze(state)
        findings = res["findings"]

        # Revenue: 100 -> 100 -> 100 => Flat
        rev_trend = [f for f in findings if f.metric == "revenue_trend"][0]
        assert "Flat" in rev_trend.calculation

        # Gross Profit: 2023: 100 -> 2024: 90 -> 2025: 80 => Consistent Decrease
        gp_trend = [f for f in findings if f.metric == "gross_profit_trend"][0]
        assert "Consistent Decrease" in gp_trend.calculation

        # Operating Income: 2023: 90 -> 2024: 120 -> 2025: 100 => Volatile
        op_trend = [f for f in findings if f.metric == "operating_income_trend"][0]
        assert "Volatile" in op_trend.calculation


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

    async def test_12_research_graph_guardrails_validation(self):
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
            query="Apple 2025 revenue",
            top_k=5,
            min_similarity=0.0,
        )

        assert "guardrails_validation" in final_state
        assert final_state["guardrails_validation"] is not None
        assert final_state["guardrails_validation"].passed is True
        assert final_state["status"] == "validated"
