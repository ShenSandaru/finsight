# Multi-Agent Financial Research System Using LangGraph (Sprint 9.1)

## 1. Overview & Architecture

Sprint 9.1 introduces a deterministic, multi-agent financial research workflow orchestrated by **LangGraph**. The system replaces monolithic prompt answer generation with a specialized multi-agent graph composed of five coordinated agents and structured state tracking:

```
[START]
   ↓
[Planner Node] (Decomposes research query into bounded period-specific subqueries)
   ↓
[Retriever Node] (Executes parallel searches via RetrievalService & deduplicates chunks)
   ↓
(Conditional Edge: chunks present?)
   ├─ No ──→ [No Evidence Fallback] ──→ [END]
   └─ Yes ─→ [Financial Analyzer Node] (Extracts metrics & calculates deterministic margins/growth)
               ↓
             [Citation Auditor / Critic Node] (Validates calculated figures against chunk contents)
               ↓
             (Conditional Edge: audit passed?)
               ├─ No ──→ [No Evidence Fallback] ──→ [END]
               └─ Yes ─→ [Synthesis Node] (Generates grounded financial answer with [SOURCE N] citations)
                           ↓
                         [END]
```

---

## 2. Core Agent Roles & Implementation

### 1. State Definition (`app/agents/state.py`)
- `ResearchState`: A TypedDict storing `original_query`, `standalone_query`, `sub_queries`, `retrieved_chunks`, `findings`, `citation_audit`, `final_answer`, `citations`, and `grounded`.
- `FinancialFinding`: Pydantic model for structured financial figures and mathematical formulas.
- `CitationAuditResult`: Comprehensive audit report validating chunk provenance.

### 2. Planner Agent (`app/agents/planner.py`)
- Analyzes research questions to extract fiscal years (e.g. `2025`, `2024`) and periods (`Q1`, `Q2`).
- Decomposes multi-period comparisons into bounded subqueries (capped at `AGENT_MAX_SUBQUERIES=4`).

### 3. Retriever Agent (`app/agents/retriever.py`)
- Reuses `RetrievalService.search()`.
- Executes retrieval for all planner subqueries and deduplicates results by `chunk_id`, keeping the highest similarity score.

### 4. Financial Analyzer Agent (`app/agents/financial_analyzer.py`)
- Extracts raw balance sheet, income statement, and cash flow metrics.
- Deterministically computes financial ratios (Gross Margin %, Net Margin %) and YoY Growth rates using Python arithmetic to eliminate LLM mathematical hallucinations.

### 5. Citation Auditor / Critic Agent (`app/agents/citation_auditor.py`)
- Verifies every finding against the retrieved chunk records in PostgreSQL.
- Rejects findings referencing invalid chunk IDs or hallucinated values.

### 6. Synthesis Agent (`app/agents/synthesis.py`)
- Assembles grounded context containing retrieved chunk excerpts and audited financial findings.
- Invokes `GenerationService` and enforces `validate_and_clean_citations()` to preserve structured citations.

---

## 3. Verification & Test Results

### Offline Test Suite (`backend/tests/test_agent_system.py` & Full Pytest Suite)
- **Total Tests Passing**: 207 passed (100% pass rate).
- Full coverage across individual nodes (Planner, Retriever, Analyzer, Auditor, Synthesis) and end-to-end StateGraph routing.

### Docker E2E Verification (`backend/tests/e2e_test.py`)
- **E2E 1**: 2-page PDF parsed, chunked, and indexed with 1536-dim embeddings.
- **E2E 2**: Malformed PDF error handling (`pending` -> `failed`).
- **E2E 3**: TXT file ingestion & indexing.
- **E2E 4**: Financial PDF tables classified & indexed.
- **E2E 5**: HNSW vector cosine similarity search verification.
- **E2E 6**: Grounded single-turn RAG with citations.
- **E2E 7**: Multi-turn conversation memory, follow-up rewriting, and session isolation.
- **E2E 8**: **LangGraph Multi-Agent Financial Research System** verified end-to-end in Docker.
