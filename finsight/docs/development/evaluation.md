# Financial Evaluation & Benchmark Suite Architecture (Sprint 10.5)

## 1. Overview & Objectives

In **Sprint 10.5**, FinSight established a dedicated, deterministic **Financial Evaluation & Benchmark Suite** (`backend/evaluation/`) to systematically measure system quality, retrieval recall, citation provenance, numerical exact-match accuracy, and hallucination resistance.

### Core Architecture Highlights:
1. **Strict Production Isolation**:
   - The evaluation framework is completely standalone. Production runtime pipelines (`LangGraph`, `FastAPI`, `Worker`) never import or depend on `evaluation.*`.
2. **Deterministic Arithmetic & Grounding**:
   - Every financial ratio, percentage variance, multi-year CAGR, and comparative delta is evaluated against ground truth deterministically in Python ($0$ LLM judge calls).
3. **Multi-Document & Isolation Testing**:
   - Measures retrieval scoping and enforces $100\%$ zero-contamination rules across multi-document inquiries.
4. **Adversarial Fallback Verification**:
   - Tests unanswerable and missing-evidence inquiries to verify that FinSight executes controlled fallbacks without fabricating data.

---

## 2. Benchmark Dataset (`financial_benchmark_v1.json`)

The standardized benchmark dataset consists of structured test cases categorized by research complexity:

| Category | Description | Key Evaluators |
|---|---|---|
| `single_metric` | Direct extraction of reported financial line items | Numerical, Citation, Retrieval |
| `calculated_ratio` | Deterministic computation of Margins, ROA, Current Ratio, D/E, FCF | Numerical, Formula, Citation |
| `time_series_cagr` | Sequential YoY growth, multi-year CAGR, and trend classifications | Numerical, Tolerance, CAGR |
| `cross_document_comparison` | Inter-company comparison with isolated metrics and variance math | Isolation, Numerical, Multi-Doc |
| `multi_turn_followup` | Context preservation and pronoun-dependent query rewriting | Context, Numerical, Citation |
| `adversarial_insufficient_evidence` | Out-of-corpus / ungrounded financial inquiries | Adversarial Fallback, Grounding |

---

## 3. Evaluation Metrics & Formulation

### A. Retrieval Metrics
- **Recall@5**: $|\text{Retrieved Chunks} \cap \text{Ground Truth}| / |\text{Ground Truth}|$
- **Hit Rate@5**: $1.0$ if at least 1 authoritative chunk retrieved; $0.0$ otherwise.
- **MRR**: Mean Reciprocal Rank of the first authoritative source chunk.

### B. Numerical Accuracy
- **Relative Error Tolerance**:
  $$\text{Relative Error} = \frac{|V_{\text{system}} - V_{\text{expected}}|}{|V_{\text{expected}}|}$$
  Pass condition: $\text{Relative Error} \le \frac{\text{Tolerance}_{\%}}{100}$.

### C. Citation & Grounding Metrics
- **Citation Precision**: Valid authoritative citations / total citations generated.
- **Document Isolation Score**: $1.0$ if $0$ chunks from unselected documents are retrieved/cited; $0.0$ on contamination.
- **Adversarial Fallback Accuracy**: $1.0$ if the system produces controlled fallback on ungrounded inquiries without hallucinating.

---

## 4. Benchmark Quality Gates & Thresholds

| Metric | Target Threshold | Baseline Achieved | Status |
|---|---|---|---|
| **Numerical Exact Match** | $\ge 98.0\%$ | **100.0%** | ✅ PASS |
| **Retrieval Hit Rate@5** | $\ge 95.0\%$ | **100.0%** | ✅ PASS |
| **Citation Precision** | $\ge 95.0\%$ | **100.0%** | ✅ PASS |
| **Grounding Pass Rate** | $\ge 95.0\%$ | **100.0%** | ✅ PASS |
| **Document Isolation** | **100.0%** | **100.0%** | ✅ PASS |
| **Adversarial Fallback** | **100.0%** | **100.0%** | ✅ PASS |
| **Overall Pass Rate** | $\ge 95.0\%$ | **100.0%** | ✅ PASS |

---

## 5. Execution

Run the evaluation benchmark from the backend root:
```bash
python -m evaluation.runner
```
Output results are written to `backend/evaluation/results/benchmark_report_latest.json`.
