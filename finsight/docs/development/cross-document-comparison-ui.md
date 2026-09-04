# Phase 11.8 — Cross-Document Comparison UX

## 1. Overview & Architecture Boundary

Phase 11.8 implements institutional cross-document financial comparison on top of FinSight's existing multi-agent research and deterministic financial analysis architecture.

### Sole Backend Authority for Financial Analytics
The FinSight backend remains the sole authority for financial calculations and variance determinations:
* **The frontend NEVER calculates financial variances**: No absolute variance (`diff = a - b`), no percentage change (`pct = (a - b) / b * 100`), no margins, no ratios, and no CAGR are computed on the client.
* **Authoritative Finding Ingestion**: The frontend consumes:
  * `{metric}_absolute_difference` as the authoritative backend absolute variance.
  * `{metric}_comparison` as the authoritative backend percentage variance.
  * Document-scoped `{metric}` findings as isolated filing values.
* **Informational Provenance**: The `calculation` string returned by the backend (e.g., `((245000 - 412000) / 412000) * 100 [DocB vs DocA]`) is treated as provenance metadata and never parsed for client-side arithmetic.

---

## 2. API Contract & Research Reuse

### No Dedicated Comparison API
The audit established that there is no dedicated `/api/v1/comparisons` endpoint. Comparison is conducted through the existing multi-turn conversation research query API:

```http
POST /api/v1/conversations/{session_id}/query
Content-Type: application/json

{
  "query": "Compare revenue, gross margin, and profitability across the selected filings.",
  "document_ids": [
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222"
  ]
}
```

### Backend Multi-Document Processing Flow
1. Research request receives `document_ids: string[]` (minimum 2 documents for cross-filing comparisons).
2. LangGraph nodes retrieve filing chunks scoped to the selected IDs.
3. `FinancialAnalyzerNode.compute_cross_document_comparisons` detects common `(metric, period)` combinations across distinct filings and emits:
   - Base metric findings associated with individual `document_id`s.
   - `{metric}_absolute_difference` with `document_id: null` and merged `source_chunk_ids`.
   - `{metric}_comparison` with `document_id: null` and merged `source_chunk_ids`.
4. Narrative synthesis cites retrieved chunks using `[SOURCE N]` markers.

---

## 3. UI Implementation Details

### Document Selection (`ComparisonSelector`)
* Location: [comparison-selector.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/components/comparison/comparison-selector.tsx)
* Reuses existing global Zustand store: `useUiStore.selectedDocumentIds`.
* Enforces minimum selection requirement: At least 2 indexed filings must be selected before comparison execution is enabled.
* Displays filing metadata: Title, filename, format badge, chunk count, and selected filing badges with clear removal controls.

### Comparison Workspace (`/compare`)
* Location: [page.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/app/compare/page.tsx)
* Integrated into existing `AppShell` with active sidebar link.
* Presets: Preconfigured comparative inquiry shortcuts (Comprehensive, Revenue & Margins, Balance Sheet & Solvency).
* Query customization: Full user editing of comparative research prompt.
* Loading state: "Analyzing selected filings..." banner indicating multi-filing scope without fabricated progress bars.
* Error state: Informative alert banner handling network errors and backend service unavailability.

### Institutional Comparison Table (`ComparisonTable`)
* Location: [comparison-table.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/components/comparison/comparison-table.tsx)
* Columns:
  1. **Metric**: Formatted metric title with calculation provenance tooltip.
  2. **Period**: Fiscal period cleanly parsed from backend period keys.
  3. **Document Columns**: Side-by-side columns populated exclusively with backend findings matching document IDs. Cells without data remain cleanly marked as `—`.
  4. **Difference**: Authoritative `{metric}_absolute_difference` formatted via `formatFinancialValue`.
  5. **Variance**: Authoritative `{metric}_comparison` rendered with directional indicator.
  6. **Evidence**: Citation action button linking to source chunks.

### Neutral Variance Indicator (`VarianceIndicator`)
* Location: [variance-indicator.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/components/comparison/variance-indicator.tsx)
* Directional glyphs: `↑` (positive), `↓` (negative), `→` (flat/zero).
* Avoids value judgments (e.g. does not label debt increases as "improving").
* Screen-reader accessible: Includes accessible text labels (`aria-label`).

### Evidence & Provenance Integration
* Reuses Phase 11.5 `useUiStore.openCitationDrawer(chunkId)`.
* Citation pills in synthesis narrative (`[SOURCE N]`) directly open the source chunk inspector.
* Table evidence buttons trigger the citation drawer for the merged backend `source_chunk_ids`.

### Cross-Page Navigation
* **Documents Page** ([documents/page.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/app/documents/page.tsx)): Displays a "Compare Filings (N)" button when 2+ filings are selected in the document list.
* **Research Context Bar** ([selected-document-context.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/components/research/selected-document-context.tsx)): Displays a compact "Compare" button when multiple documents are in scope.
* **Sidebar** ([sidebar.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/components/layout/sidebar.tsx)): Active route without "Soon" badge.

---

## 4. Verification & Testing

* Full MSW mock coverage with realistic multi-document comparison payloads in `tests/mocks/data.ts` and `tests/mocks/handlers.ts`.
* 15 comprehensive tests in [comparison-ui.test.tsx](file:///d:/Portfolio%20soft%20projects/finsight/finsight/frontend/tests/comparison-ui.test.tsx).
* Verification commands executed:
  * `npm test`: 124/124 tests passing across 10 test files.
  * `npm run typecheck`: Passed with zero TypeScript diagnostic errors.
  * `npm run lint`: Passed with zero ESLint errors or warnings.
  * `npm run build`: Production bundle builds successfully.
