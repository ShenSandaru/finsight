"""Unit test suite for FinSight Evaluation Framework (Sprint 10.5)."""

import uuid
import pytest
from evaluation.schemas import (
    BenchmarkItem,
    ExpectedMetric,
    QualityThresholds,
    BenchmarkReport,
)
from evaluation.evaluators import (
    RetrievalEvaluator,
    NumericalEvaluator,
    CitationEvaluator,
    GroundingEvaluator,
    MultiDocumentIsolationEvaluator,
)
from app.agents.state import FinancialFinding
from app.services.rag_service import SourceCitation


class DummyChunk:
    def __init__(self, id: uuid.UUID, content: str, statement_type: str = "income_statement", document_id: uuid.UUID | None = None):
        self.id = id
        self.content = content
        self.metadata = {"statement_type": statement_type}
        self.statement_type = statement_type
        self.document_id = document_id


def create_dummy_citation(
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    statement_type: str = "income_statement",
) -> SourceCitation:
    return SourceCitation(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=document_id,
        page_number=1,
        chunk_type="table",
        similarity=0.95,
        statement_type=statement_type,
        fiscal_periods=["2025"],
    )


class TestEvaluationFrameworkUnit:

    def test_01_retrieval_evaluator_exact_ids(self):
        c1, c2, c3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        retrieved = [DummyChunk(c1, "Text 1"), DummyChunk(c2, "Text 2")]
        res = RetrievalEvaluator.evaluate(
            retrieved_chunks=retrieved,
            ground_truth_chunk_ids={c1, c3},
            top_k=5,
        )
        assert res.passed is True
        assert res.details["recall"] == 0.5
        assert res.details["hit_rate"] == 1.0
        assert res.details["mrr"] == 1.0

    def test_02_retrieval_evaluator_empty_ground_truth(self):
        retrieved = [DummyChunk(uuid.uuid4(), "Text 1")]
        res = RetrievalEvaluator.evaluate(
            retrieved_chunks=retrieved,
            ground_truth_chunk_ids=set(),
            top_k=5,
        )
        assert res.passed is True
        assert res.score == 1.0

    def test_03_retrieval_evaluator_semantic_matching(self):
        retrieved = [
            DummyChunk(uuid.uuid4(), "Consolidated Statement of Operations with Total Revenue of 1000", statement_type="income_statement"),
            DummyChunk(uuid.uuid4(), "Balance sheet data", statement_type="balance_sheet"),
        ]
        res = RetrievalEvaluator.evaluate(
            retrieved_chunks=retrieved,
            expected_keywords=["Total Revenue"],
            expected_statements=["income_statement"],
            top_k=5,
        )
        assert res.passed is True
        assert res.details["hit_rate"] == 1.0
        assert res.details["mrr"] == 1.0

    def test_04_retrieval_evaluator_no_chunks(self):
        res = RetrievalEvaluator.evaluate(retrieved_chunks=[], top_k=5)
        assert res.passed is False
        assert res.score == 0.0

    def test_05_numerical_evaluator_exact_match(self):
        findings = [
            FinancialFinding(metric="revenue", period="2025", value=1000.0, unit="$"),
            FinancialFinding(metric="operating_margin", period="2025", value=20.0, unit="%"),
        ]
        expected = [
            ExpectedMetric(metric="revenue", period="2025", expected_value=1000.0, unit="$"),
            ExpectedMetric(metric="operating_margin", period="2025", expected_value=20.0, unit="%"),
        ]
        res = NumericalEvaluator.evaluate(findings, expected)
        assert res.passed is True
        assert res.score == 1.0

    def test_06_numerical_evaluator_tolerance(self):
        findings = [
            FinancialFinding(metric="revenue_cagr", period="2022_to_2025", value=11.114, unit="%"),
        ]
        expected = [
            ExpectedMetric(metric="revenue_cagr", period="2022_to_2025", expected_value=11.11, unit="%", tolerance_pct=0.1),
        ]
        res = NumericalEvaluator.evaluate(findings, expected)
        assert res.passed is True
        assert res.score == 1.0

    def test_07_numerical_evaluator_zero_expected_value(self):
        findings = [
            FinancialFinding(metric="net_loss", period="2025", value=0.0, unit="$"),
        ]
        expected = [
            ExpectedMetric(metric="net_loss", period="2025", expected_value=0.0, unit="$"),
        ]
        res = NumericalEvaluator.evaluate(findings, expected)
        assert res.passed is True
        assert res.score == 1.0

    def test_08_numerical_evaluator_unit_mismatch(self):
        findings = [
            FinancialFinding(metric="revenue", period="2025", value=1000.0, unit="%"),  # should be $
        ]
        expected = [
            ExpectedMetric(metric="revenue", period="2025", expected_value=1000.0, unit="$"),
        ]
        res = NumericalEvaluator.evaluate(findings, expected)
        assert res.passed is False
        assert res.score == 0.0

    def test_09_numerical_evaluator_missing_metric(self):
        findings = [
            FinancialFinding(metric="revenue", period="2025", value=1000.0, unit="$"),
        ]
        expected = [
            ExpectedMetric(metric="revenue", period="2025", expected_value=1000.0, unit="$"),
            ExpectedMetric(metric="operating_margin", period="2025", expected_value=20.0, unit="%"),
        ]
        res = NumericalEvaluator.evaluate(findings, expected)
        assert res.passed is False
        assert res.score == 0.5

    def test_10_citation_evaluator_valid(self):
        c1 = create_dummy_citation(statement_type="income_statement")
        res = CitationEvaluator.evaluate([c1], requires_citations=True, min_citations=1, expected_statements=["income_statement"])
        assert res.passed is True
        assert res.score == 1.0

    def test_11_citation_evaluator_missing_citation(self):
        res = CitationEvaluator.evaluate([], requires_citations=True, min_citations=1)
        assert res.passed is False
        assert res.score == 0.0

    def test_12_citation_evaluator_unexpected_statement(self):
        c1 = create_dummy_citation(statement_type="balance_sheet")
        res = CitationEvaluator.evaluate([c1], requires_citations=True, min_citations=1, expected_statements=["income_statement"])
        assert res.passed is False
        assert res.score == 0.0

    def test_13_grounding_evaluator_standard_pass(self):
        c1 = create_dummy_citation()
        res = GroundingEvaluator.evaluate(
            answer="In 2025, total revenue was $1,000 million with operating margin of 20.0%.",
            findings=[],
            citations=[c1],
            grounded_flag=True,
            allow_insufficient_evidence=False,
            expected_substrings=["1,000", "20.0%"],
        )
        assert res.passed is True
        assert res.score == 1.0

    def test_14_grounding_evaluator_missing_content_fail(self):
        c1 = create_dummy_citation()
        res = GroundingEvaluator.evaluate(
            answer="In 2025, total revenue was $1,000 million.",
            findings=[],
            citations=[c1],
            grounded_flag=True,
            allow_insufficient_evidence=False,
            expected_substrings=["20.0%"],  # missing
        )
        assert res.passed is False

    def test_15_grounding_evaluator_adversarial_fallback(self):
        res = GroundingEvaluator.evaluate(
            answer="I could not find enough relevant information to answer this question.",
            findings=[],
            citations=[],
            grounded_flag=False,
            allow_insufficient_evidence=True,
        )
        assert res.passed is True
        assert res.score == 1.0

    def test_16_grounding_evaluator_adversarial_hallucination_fail(self):
        c1 = create_dummy_citation()
        res = GroundingEvaluator.evaluate(
            answer="The company held 500 Bitcoins in 2019.",
            findings=[],
            citations=[c1],
            grounded_flag=True,
            allow_insufficient_evidence=True,
        )
        assert res.passed is False

    def test_17_multi_document_isolation_pass(self):
        doc_a = uuid.uuid4()
        doc_b = uuid.uuid4()
        chunks = [
            DummyChunk(uuid.uuid4(), "A", document_id=doc_a),
            DummyChunk(uuid.uuid4(), "B", document_id=doc_b),
        ]
        citations = [
            create_dummy_citation(document_id=doc_a),
            create_dummy_citation(document_id=doc_b),
        ]
        res = MultiDocumentIsolationEvaluator.evaluate(chunks, citations, scoped_document_ids=[doc_a, doc_b])
        assert res.passed is True
        assert res.score == 1.0

    def test_18_multi_document_isolation_contamination_fail(self):
        doc_a = uuid.uuid4()
        doc_b = uuid.uuid4()
        doc_c = uuid.uuid4()  # Unselected
        chunks = [
            DummyChunk(uuid.uuid4(), "A", document_id=doc_a),
            DummyChunk(uuid.uuid4(), "C", document_id=doc_c),
        ]
        citations = [
            create_dummy_citation(document_id=doc_a),
        ]
        res = MultiDocumentIsolationEvaluator.evaluate(chunks, citations, scoped_document_ids=[doc_a, doc_b])
        assert res.passed is False
        assert res.score == 0.0

    def test_19_quality_thresholds_pass_and_fail(self):
        t = QualityThresholds()
        report_good = BenchmarkReport(
            total_benchmark_cases=10,
            passed_cases=10,
            failed_cases=0,
            overall_pass_rate=1.0,
            retrieval_recall_at_5=1.0,
            retrieval_hit_rate=1.0,
            retrieval_mrr=1.0,
            numerical_exact_match=1.0,
            citation_precision=1.0,
            grounding_pass_rate=1.0,
            multi_document_isolation=1.0,
            adversarial_fallback_accuracy=1.0,
            cagr_trend_accuracy=1.0,
            thresholds_passed=True,
            threshold_results={},
            category_breakdown={},
        )
        assert report_good.overall_pass_rate >= t.min_overall_pass_rate
        assert report_good.numerical_exact_match >= t.min_numerical_exact_match
