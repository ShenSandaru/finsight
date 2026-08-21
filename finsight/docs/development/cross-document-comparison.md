# Multi-Document & Cross-Company Financial Comparison Architecture (Sprint 10.3)

## 1. Overview & Objectives

In **Sprint 10.3**, FinSight was enhanced to support **multi-document and cross-company financial comparisons** natively across its vector retrieval layer, multi-agent LangGraph workflow, and conversational endpoints.

Prior to Sprint 10.3, vector retrieval and financial metric extraction operated either globally across all indexed documents or were scoped to a single `document_id`. Sprint 10.3 introduces:
1. **Multi-Document Filtered Retrieval**: Vector similarity queries can be strictly bounded to an explicit list of documents (`document_ids: list[UUID]`), preventing unselected documents from polluting the context window.
2. **Document-Scoped Metric Isolation**: Raw financial metrics (`revenue`, `gross_profit`, `net_income`, etc.) are partitioned by `(document_id, period, metric)` so figures from distinct companies or filings never collide or falsely aggregate.
3. **Deterministic Cross-Document Comparative Calculations**: For common metrics and periods across distinct documents, the system computes:
   - **Absolute Difference**: $\Delta_{\text{abs}} = \text{Value}_B - \text{Value}_A$
   - **Percentage Difference**: $\Delta_{\%} = \left(\frac{\text{Value}_B - \text{Value}_A}{|\text{Value}_A|}\right) \times 100$
4. **Dual Provenance & Citation Integrity**: Comparison findings merge source chunk IDs from both documents ($A$ and $B$), enabling `CitationAuditor` and Guardrails output validation to verify evidence from all comparative parties.
5. **Zero Additional LLM Calls**: All filtering, metric isolation, ratio derivations, and comparative math are executed using deterministic Python logic.

---

## 2. Architectural Flow & Pipeline

```mermaid
graph TD
    UserQuery[User Comparison Query & document_ids] --> ConvRoute[POST /conversations/{id}/query]
    ConvRoute --> ConvService[ConversationService.process_query]
    ConvService --> ResService[FinancialResearchService.execute_research]
    ResService --> Planner[PlannerNode: Multi-Query Decomposition]
    Planner --> Retriever[RetrieverNode: search top_k with Chunk.document_id.in_]
    Retriever --> Analyzer[FinancialAnalyzerNode: Isolate by doc_id & Compute Diff]
    Analyzer --> Auditor[CitationAuditorNode: Validate Chunks from Doc A & Doc B]
    Auditor --> Synthesis[SynthesisNode: Single Gemini Grounded Call]
    Synthesis --> Guardrails[Guardrails Validation Node]
    Guardrails --> Response[Final Answer + Multi-Doc Citations]
```

---

## 3. Key Components & Implementation Details

### 3.1 Retrieval Layer (`retrieval_service.py`)
- Extended `RetrievalService.search()` signature with `document_ids: list[UUID] | None = None`.
- If `document_ids` is provided, applies SQLAlchemy `Chunk.document_id.in_(document_ids)`.
- If single `document_id` is provided, applies `Chunk.document_id == document_id` for complete backward compatibility.

### 3.2 Request Schemas & API Endpoints
- `SearchRequest`, `RAGRequest`, and `ConversationQueryRequest` include optional `document_ids: list[UUID] | None`.
- API route handlers (`/search`, `/rag/query`, `/conversations/{session_id}/query`) forward `document_ids` seamlessly.

### 3.3 State Schema & Model Provenance (`state.py`)
- `FinancialFinding` tracks `document_id: UUID | None`.
- `ResearchState` tracks `document_ids: list[UUID] | None`.

### 3.4 Multi-Document Analysis & Comparison (`financial_analyzer.py`)
1. **Extraction**: `extract_metrics_from_text(content, chunk_id, document_id)` tags every extracted finding with the chunk's parent `document_id`.
2. **Document-Level Derivations**: `compute_ratios_and_growth_for_doc(doc_findings, doc_id)` computes intra-document ratios (Margins, ROA, Current Ratio, Debt-to-Equity, FCF), sequential YoY, and CAGR.
3. **Cross-Document Derivations**: `compute_cross_document_comparisons(all_findings)` pairs identical metrics across documents for the same period:
   - Sets metric name: `{metric}_absolute_difference` and `{metric}_comparison`.
   - Sets period token: `{period}_docB_vs_docA`.
   - Sets provenance: `source_chunk_ids = list(set(src_a + src_b))`.

---

## 4. Verification & Testing

1. **Unit & Integration Suite**:
   - `test_18b_multi_document_ids_filtering`: Tests PostgreSQL pgvector multi-document filtering and isolation.
   - `test_05g_cross_document_isolation_and_comparison`: Tests metric separation between Doc A ($100) and Doc B ($150), verifying $50.00 difference and $+50.0\%$ comparison with combined chunk IDs.
   - **229 Local Pytest Tests Passing**.
2. **Docker End-to-End Suite**:
   - **E2E 12**: Uploads Apple 10-K (Doc A) and Microsoft 10-K (Doc B), queries cross-document comparison, validates multi-document chunk retrieval, deterministic comparative calculation, multi-doc citation verification, and Guardrails validation.
   - **12/12 Docker E2E Scenarios Passing**.
