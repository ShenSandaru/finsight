"""Deterministic evaluators for FinSight Financial Evaluation Suite (Sprint 10.5)."""

from typing import Any
import uuid

from evaluation.schemas import (
    BenchmarkItem,
    ExpectedMetric,
    MetricResult,
)


class RetrievalEvaluator:
    """Evaluates vector retrieval quality (Recall@K, Hit Rate@K, MRR)."""

    @staticmethod
    def evaluate(
        retrieved_chunks: list[Any],
        expected_keywords: list[str] | None = None,
        expected_statements: list[str] | None = None,
        ground_truth_chunk_ids: set[uuid.UUID] | None = None,
        top_k: int = 5,
    ) -> MetricResult:
        if not retrieved_chunks:
            return MetricResult(
                metric_name="retrieval",
                passed=False,
                score=0.0,
                details={"recall": 0.0, "hit_rate": 0.0, "mrr": 0.0},
                error_message="No chunks retrieved",
            )

        top_chunks = retrieved_chunks[:top_k]

        # Mode A: Chunk ID matching if ground-truth IDs exist
        if ground_truth_chunk_ids:
            retrieved_ids = {getattr(c, "id", None) or getattr(c, "chunk_id", None) for c in top_chunks}
            retrieved_ids.discard(None)
            matches = retrieved_ids.intersection(ground_truth_chunk_ids)
            recall = len(matches) / len(ground_truth_chunk_ids) if ground_truth_chunk_ids else 1.0
            hit_rate = 1.0 if matches else 0.0

            # Compute MRR
            mrr = 0.0
            for idx, c in enumerate(top_chunks, 1):
                cid = getattr(c, "id", None) or getattr(c, "chunk_id", None)
                if cid in ground_truth_chunk_ids:
                    mrr = 1.0 / idx
                    break

            passed = hit_rate >= 1.0
            return MetricResult(
                metric_name="retrieval",
                passed=passed,
                score=recall,
                details={"recall": recall, "hit_rate": hit_rate, "mrr": mrr},
            )

        # Mode B: Semantic statement & keyword matching
        hits = 0
        total_targets = (len(expected_keywords or [])) + (len(expected_statements or []))
        if total_targets == 0:
            return MetricResult(metric_name="retrieval", passed=True, score=1.0, details={"hit_rate": 1.0})

        first_hit_rank = 0
        for idx, c in enumerate(top_chunks, 1):
            content = getattr(c, "content", "")
            metadata = getattr(c, "metadata", {}) or {}
            stmt = metadata.get("statement_type") or getattr(c, "statement_type", "")

            matched_this_chunk = False
            if expected_keywords:
                for kw in expected_keywords:
                    if kw.lower() in content.lower():
                        hits += 1
                        matched_this_chunk = True

            if expected_statements:
                for st in expected_statements:
                    if st.lower() in str(stmt).lower():
                        hits += 1
                        matched_this_chunk = True

            if matched_this_chunk and first_hit_rank == 0:
                first_hit_rank = idx

        hit_rate = 1.0 if hits > 0 else 0.0
        recall = min(1.0, hits / total_targets) if total_targets > 0 else 1.0
        mrr = (1.0 / first_hit_rank) if first_hit_rank > 0 else 0.0

        return MetricResult(
            metric_name="retrieval",
            passed=hit_rate >= 1.0,
            score=recall,
            details={"recall": recall, "hit_rate": hit_rate, "mrr": mrr},
        )


class NumericalEvaluator:
    """Evaluates numerical correctness of extracted metrics, ratios, CAGR, and cross-doc diffs."""

    @staticmethod
    def evaluate(
        system_findings: list[Any],
        expected_metrics: list[ExpectedMetric] | None,
    ) -> MetricResult:
        if not expected_metrics:
            return MetricResult(metric_name="numerical", passed=True, score=1.0, details={"evaluated": 0})

        if not system_findings:
            return MetricResult(
                metric_name="numerical",
                passed=False,
                score=0.0,
                error_message="No financial findings produced by system",
            )

        passed_count = 0
        details = []

        for expected in expected_metrics:
            # Find matching finding by metric name and period
            match = None
            clean_exp_m = expected.metric.lower().replace("_", "").replace(" ", "")
            exp_p = str(expected.period).lower()

            for sf in system_findings:
                clean_m = getattr(sf, "metric", "").lower().replace("_", "").replace(" ", "")
                p_name = str(getattr(sf, "period", "")).lower()
                name_match = (clean_m == clean_exp_m) or (clean_exp_m in clean_m) or (clean_m in clean_exp_m)
                period_match = (p_name == exp_p) or (exp_p in p_name) or (p_name in exp_p)
                if name_match and period_match:
                    match = sf
                    break

            if not match:
                details.append({
                    "metric": expected.metric,
                    "period": expected.period,
                    "status": "missing_metric",
                    "expected": expected.expected_value,
                })
                continue

            sys_val = getattr(match, "value", None)
            sys_unit = getattr(match, "unit", "")

            # Strict unit mismatch
            if expected.unit and expected.unit.lower() != str(sys_unit).lower():
                details.append({
                    "metric": expected.metric,
                    "period": expected.period,
                    "status": "unit_mismatch",
                    "expected_unit": expected.unit,
                    "actual_unit": sys_unit,
                })
                continue

            if not isinstance(sys_val, (int, float)):
                details.append({
                    "metric": expected.metric,
                    "period": expected.period,
                    "status": "non_numeric_value",
                    "actual": sys_val,
                })
                continue

            if expected.expected_value == 0.0:
                is_correct = abs(sys_val) <= 1e-4
            else:
                rel_error = abs(sys_val - expected.expected_value) / abs(expected.expected_value)
                abs_diff = abs(sys_val - expected.expected_value)
                is_correct = (rel_error <= max(expected.tolerance_pct, 5.0) / 100.0) or (abs_diff <= 0.05)

            if is_correct:
                passed_count += 1
                details.append({
                    "metric": expected.metric,
                    "period": expected.period,
                    "status": "pass",
                    "value": sys_val,
                })
            else:
                details.append({
                    "metric": expected.metric,
                    "period": expected.period,
                    "status": "tolerance_exceeded",
                    "expected": expected.expected_value,
                    "actual": sys_val,
                })

        score = (passed_count / len(expected_metrics)) if expected_metrics else 1.0
        passed = (passed_count == len(expected_metrics))

        return MetricResult(
            metric_name="numerical",
            passed=passed,
            score=score,
            details={"matches": details, "passed": passed_count, "total": len(expected_metrics)},
            error_message=None if passed else f"{len(expected_metrics) - passed_count} metrics failed accuracy check",
        )


class CitationEvaluator:
    """Evaluates citation correctness, provenance completeness, and hallucination resistance."""

    @staticmethod
    def evaluate(
        citations: list[Any],
        requires_citations: bool = True,
        min_citations: int = 1,
        expected_statements: list[str] | None = None,
    ) -> MetricResult:
        if not requires_citations:
            return MetricResult(metric_name="citation", passed=True, score=1.0, details={"required": False})

        if not citations or len(citations) < min_citations:
            return MetricResult(
                metric_name="citation",
                passed=False,
                score=0.0,
                error_message=f"Insufficient citations: got {len(citations) if citations else 0}, expected >={min_citations}",
            )

        valid_citations = 0
        details = []

        for idx, c in enumerate(citations):
            chunk_id = getattr(c, "chunk_id", None)
            stmt_type = getattr(c, "statement_type", None)

            if not chunk_id:
                details.append({"citation_index": idx, "status": "missing_chunk_id"})
                continue

            # Verify statement type if required
            if expected_statements and stmt_type:
                if not any(exp.lower() in str(stmt_type).lower() for exp in expected_statements):
                    details.append({"citation_index": idx, "status": "unexpected_statement", "actual": stmt_type})
                    continue

            valid_citations += 1
            details.append({"citation_index": idx, "status": "valid", "chunk_id": str(chunk_id)})

        precision = valid_citations / len(citations) if citations else 0.0
        passed = (valid_citations >= min_citations) and (precision > 0.0)

        return MetricResult(
            metric_name="citation",
            passed=passed,
            score=precision,
            details={"valid_citations": valid_citations, "total_citations": len(citations), "precision": precision},
            error_message=None if passed else "One or more citations failed provenance validation",
        )


class GroundingEvaluator:
    """Evaluates answer grounding, claim support, and adversarial fallback behavior."""

    @staticmethod
    def evaluate(
        answer: str,
        findings: list[Any],
        citations: list[Any],
        grounded_flag: bool,
        allow_insufficient_evidence: bool = False,
        expected_substrings: list[str] | None = None,
    ) -> MetricResult:
        # Case 1: Adversarial Insufficient Evidence
        if allow_insufficient_evidence:
            ans_lower = (answer or "").lower()
            is_insufficient = (
                not grounded_flag
                or "could not find enough relevant information" in ans_lower
                or "insufficient evidence" in ans_lower
                or len(citations) == 0
            ) and not (grounded_flag and len(citations) > 0 and "could not find enough" not in ans_lower and "insufficient evidence" not in ans_lower)
            return MetricResult(
                metric_name="grounding",
                passed=is_insufficient,
                score=1.0 if is_insufficient else 0.0,
                details={"adversarial_fallback_verified": is_insufficient},
                error_message=None if is_insufficient else "Failed adversarial fallback: system claimed evidence for unanswerable question",
            )

        # Case 2: Standard Grounded Response
        if not grounded_flag or not answer.strip():
            return MetricResult(
                metric_name="grounding",
                passed=False,
                score=0.0,
                error_message="Answer not marked as grounded or is empty",
            )

        if not citations:
            return MetricResult(
                metric_name="grounding",
                passed=False,
                score=0.0,
                error_message="Grounded answer produced 0 source citations",
            )

        # Substring verification across answer or serialized findings
        missing_substrings = []
        if expected_substrings:
            findings_text = " ".join([f"{getattr(f, 'metric', '')} {getattr(f, 'value', '')} {getattr(f, 'period', '')}" for f in (findings or [])])
            full_context = f"{answer} {findings_text}".lower()
            for sub in expected_substrings:
                clean_sub = sub.lower().replace(",", "").replace("$", "").replace("%", "")
                clean_context = full_context.replace(",", "").replace("$", "").replace("%", "")
                if clean_sub not in clean_context and sub.lower() not in full_context:
                    missing_substrings.append(sub)

        passed = len(missing_substrings) == 0
        return MetricResult(
            metric_name="grounding",
            passed=passed,
            score=1.0 if passed else 0.5,
            details={"missing_expected_substrings": missing_substrings},
            error_message=None if passed else f"Answer missed required content: {missing_substrings}",
        )


class MultiDocumentIsolationEvaluator:
    """Evaluates that zero retrieved or cited chunks originate from unselected documents."""

    @staticmethod
    def evaluate(
        retrieved_chunks: list[Any],
        citations: list[Any],
        scoped_document_ids: list[uuid.UUID | str] | None,
    ) -> MetricResult:
        if not scoped_document_ids:
            return MetricResult(metric_name="isolation", passed=True, score=1.0, details={"scoped": False})

        allowed_ids = {str(d) for d in scoped_document_ids}
        contaminated_chunks = []

        # Check retrieved chunks
        for c in retrieved_chunks:
            doc_id = getattr(c, "document_id", None)
            if doc_id and str(doc_id) not in allowed_ids:
                contaminated_chunks.append(str(doc_id))

        # Check citations
        for cit in citations:
            doc_id = getattr(cit, "document_id", None)
            if doc_id and str(doc_id) not in allowed_ids:
                contaminated_chunks.append(str(doc_id))

        passed = (len(contaminated_chunks) == 0)
        return MetricResult(
            metric_name="isolation",
            passed=passed,
            score=1.0 if passed else 0.0,
            details={"allowed_documents": list(allowed_ids), "contamination_count": len(contaminated_chunks)},
            error_message=None if passed else f"Document isolation failure: chunks from {contaminated_chunks} retrieved",
        )
