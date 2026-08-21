# Guardrails AI — Output Validation & Financial Response Safety (Sprint 9.2)

## 1. Overview & Architecture

Sprint 9.2 introduces a deterministic **Guardrails AI Output Validation Layer** directly following the LangGraph Synthesis node. Guardrails validates all AI-generated response structures, mathematical finding bounds, citation integrity, and grounding consistency before returning output to users or saving to conversation history.

```
[START]
   ↓
[Planner Node]
   ↓
[Retriever Node]
   ↓
(Conditional Edge: chunks present?)
   ├─ No ──→ [No Evidence Fallback] ──→ [END]
   └─ Yes ─→ [Financial Analyzer Node]
               ↓
             [Citation Auditor Node]
               ↓
             (Conditional Edge: audit passed?)
               ├─ No ──→ [No Evidence Fallback] ──→ [END]
               └─ Yes ─→ [Synthesis Node]
                           ↓
                         [Guardrails Output Validation Node]
                           ↓
                         [END]
```

---

## 2. Guardrails Responsibilities & Validators

### 1. Dedicated Package (`app/guardrails/`)
- **`schemas.py`**: Defines `GuardrailsValidationResult` and `ResearchResponse`.
- **`validators.py`**:
  - `StructureValidator`: Validates non-emptiness, null-safety, and length limits (`GUARDRAILS_MAX_RESPONSE_LENGTH`).
  - `FinancialFindingValidator`: Validates that every financial finding has valid `source_chunk_ids` belonging to retrieved evidence, valid non-NaN numeric values, and reasonable percentage bounds.
  - `CitationValidator`: Validates that all citations correspond to retrieved PostgreSQL chunks and strips/cleans out-of-range source markers (`[SOURCE N]`).
  - `GroundingConsistencyValidator`: Rejects any response asserting `grounded=True` when zero valid retrieved evidence or citations exist.
- **`response_guard.py`**: High-level `ResponseGuard.validate_output()` orchestration layer executing deterministic validation passes.

---

## 3. Failure Handling & Security

- **Missing / Empty Content**: Controlled fallback to `INSUFFICIENT_EVIDENCE_ANSWER` without raw exception disclosure.
- **Unsupported Findings / Citations**: Automatically filtered and cleaned; invalid markers removed.
- **Security**: Zero logging of private credentials or raw document payloads. Only structured diagnostic violation summaries are produced.
- **Deterministic**: 0 additional LLM calls; sub-millisecond execution overhead.

---

## 4. Verification Results

- **Unit & Integration Suite**: **222 passed, 0 failed** in `pytest`.
- **Dedicated Guardrails Tests**: 14 tests in `backend/tests/test_guardrails.py`.
- **Docker E2E Suite**: **E2E 1 through E2E 9 passed** in container environment (`backend/tests/e2e_test.py`).
- **Dependencies**: `pip check` confirmed clean with no broken requirements.
