"""Schemas for FinSight Financial Evaluation & Benchmark Suite (Sprint 10.5)."""

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ExpectedMetric(BaseModel):
    """Ground truth expected metric for deterministic numerical evaluation."""
    metric: str = Field(..., min_length=1, description="Metric identifier e.g. 'revenue', 'operating_margin'")
    period: str = Field(..., min_length=1, description="Target period e.g. '2025', '2022_to_2025'")
    expected_value: float = Field(..., description="Exact ground-truth numerical value")
    unit: str = Field(..., description="Unit of measurement: '$', '%', 'ratio', 'trend'")
    tolerance_pct: float = Field(0.01, ge=0.0, description="Allowed relative tolerance percentage (default: 0.01%)")
    formula: str | None = Field(None, description="Optional expected formula string")
    document_id: uuid.UUID | str | None = Field(None, description="Expected source document UUID or placeholder")


class BenchmarkItem(BaseModel):
    """Single test case in the financial evaluation benchmark dataset."""
    id: str = Field(..., min_length=1, description="Unique benchmark case ID e.g. 'BM-001'")
    category: Literal[
        "single_metric",
        "calculated_ratio",
        "time_series_cagr",
        "cross_document_comparison",
        "multi_turn_followup",
        "adversarial_insufficient_evidence",
    ] = Field(..., description="Evaluation benchmark category")
    difficulty: Literal["easy", "medium", "hard"] = Field("medium", description="Difficulty tier")
    query: str = Field(..., min_length=3, description="Financial research query to evaluate")
    document_ids: list[uuid.UUID | str] | None = Field(None, description="Scoped document UUIDs or alias references")
    conversation_turns: list[str] | None = Field(None, description="Optional preceding conversation queries for multi-turn testing")
    
    # Ground truth expectations
    expected_metrics: list[ExpectedMetric] | None = Field(None, description="Expected financial metrics/ratios")
    expected_chunk_keywords: list[str] | None = Field(None, description="Keywords expected in authoritative retrieved chunks")
    expected_statement_types: list[str] | None = Field(None, description="Expected statement types (income_statement, etc.)")
    expected_answer_contains: list[str] | None = Field(None, description="Substrings expected in the final grounded answer")
    requires_citations: bool = Field(True, description="Whether citations are strictly required")
    expected_min_citations: int = Field(1, ge=0, description="Minimum number of verified citations expected")
    allow_insufficient_evidence: bool = Field(False, description="Whether controlled fallback is the expected correct behavior")


class MetricResult(BaseModel):
    """Result of an individual metric evaluation."""
    metric_name: str
    passed: bool
    score: float = Field(..., ge=0.0, le=1.0)
    details: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class BenchmarkCaseResult(BaseModel):
    """Aggregated evaluation results for a single benchmark item."""
    benchmark_id: str
    category: str
    query: str
    passed: bool
    retrieval_result: MetricResult | None = None
    numerical_result: MetricResult | None = None
    citation_result: MetricResult | None = None
    grounding_result: MetricResult | None = None
    isolation_result: MetricResult | None = None
    execution_time_seconds: float = 0.0
    failure_reasons: list[str] = Field(default_factory=list)


class QualityThresholds(BaseModel):
    """Centralized quality gates for evaluation benchmarks."""
    min_numerical_exact_match: float = 0.98
    min_retrieval_hit_rate_at_5: float = 0.95
    min_citation_precision: float = 0.95
    min_grounding_pass_rate: float = 0.95
    min_multi_document_isolation: float = 1.00
    min_adversarial_fallback_accuracy: float = 1.00
    min_overall_pass_rate: float = 0.95


class BenchmarkReport(BaseModel):
    """Machine-readable aggregate benchmark report."""
    benchmark_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_benchmark_cases: int
    passed_cases: int
    failed_cases: int
    overall_pass_rate: float
    
    # Aggregated Metric Averages
    retrieval_recall_at_5: float
    retrieval_hit_rate: float
    retrieval_mrr: float
    numerical_exact_match: float
    citation_precision: float
    grounding_pass_rate: float
    multi_document_isolation: float
    adversarial_fallback_accuracy: float
    cagr_trend_accuracy: float
    
    # Quality Gates
    thresholds_passed: bool
    threshold_results: dict[str, bool]
    
    # Category Breakdown & Diagnostics
    category_breakdown: dict[str, dict[str, Any]]
    failures: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
