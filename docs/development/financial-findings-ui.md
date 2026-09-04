# FinSight — Phase 11.6 Financial Findings & Trend Visualization UI

## Overview

In **Phase 11.6**, we implemented the **Financial Findings & Trend Visualization UI**, exposing the structured financial findings deterministically computed by the backend's `FinancialAnalyzerNode` directly in the institutional `/research` chat workspace.

The core principle guiding this implementation:

> *"Financial calculations remain backend-owned; the frontend only formats and presents backend-provided findings."*

The frontend does **NOT** calculate financial metrics, margins, ratios, YoY growth, CAGR, or trend directions. It consumes already-verified, audited findings and provides institutional-grade presentation with dual-channel trend indicators and seamless evidence provenance integration.

---

## 1. Audit & Backend Contract Exposure

### A. Data Flow Audit
The backend already generated rich financial findings inside the LangGraph research state (`ResearchState.findings`), including:
1. **Base metrics**: e.g., `revenue`, `gross_profit`, `operating_income`, `net_income`, `total_assets`, `free_cash_flow`.
2. **Ratios & Margins**: e.g., `gross_margin`, `operating_margin`, `net_margin`, `roa`, `current_ratio`, `debt_to_equity`.
3. **Sequential YoY Growth**: `{metric}_growth` between adjacent fiscal years (unit: `%`, period: `2025_vs_2024`).
4. **Multi-Period CAGR**: `{metric}_cagr` over fiscal spans (unit: `%`, period: `2023_to_2025`).
5. **Deterministic Trend Classification**: `{metric}_trend` with value `1.0` (increase), `-1.0` (decrease), or `0.0` (flat/volatile), and a human-readable calculation summary such as `Consistent Increase: [383285 -> 394328 -> 412000]`.
6. **Audited Provenance**: Every finding maintains `source_chunk_ids: list[UUID]` linking back to indexed filing chunks.

### B. Minimal Backend Change
`ConversationQueryResponse` in `backend/app/schemas/conversation.py` previously omitted findings. We added:
* `FinancialFindingResponse` schema matching the backend model.
* `findings: list[FinancialFindingResponse] = Field(default_factory=list)` to `ConversationQueryResponse`.
* In `ConversationService.process_query`: Mapped `findings` from the LangGraph execution into the response payload.

---

## 2. Frontend Architecture & Components

Components are located in `frontend/components/finance/`:

### 1. `financial-formatter.ts` (`lib/utils/`)
Pure presentation formatting utility:
* `formatFinancialValue(value, unit)`: Formats currency (`$412.00B`, `$126.60M`, `$12.50K`, `($50.00M)` for negatives), percentages (`+46.23%`, `-7.46%`), ratios (`1.52x`), shares (`125.00M shares`), and trends without floating-point display noise.
* `formatMetricName(metric)`: Maps canonical snake_case keys (e.g. `operating_income`, `gross_margin`, `revenue_growth`, `revenue_cagr`) to institutional titles.
* `formatPeriod(period)`: Formats periods (`2025` -> `FY2025`, `2025_vs_2024` -> `FY25 vs FY24`, `2023_to_2025` -> `FY23–FY25`).
* `parseTrendFinding(finding)`: Extracts authoritative direction (`improving`, `declining`, `flat`, `volatile`), glyphs (`↑`, `↓`, `→`, `~`), and historical value sequences.
* `categorizeFinding(finding)`: Classifies findings into `metric`, `ratio`, `growth`, `cagr`, or `trend` buckets.

### 2. `metric-card.tsx`
Reusable metric card:
* Displays metric name and fiscal period tag.
* Large tabular-figure formatted value.
* Associated YoY growth badge (`+7.5% YoY` with dual-channel directional arrow and semantic color).
* Trend badge and CAGR display.
* **Evidence button**: Clickable button that calls `openCitationDrawer(finding.source_chunk_ids[0])`, seamlessly opening the Phase 11.5 Citation & Evidence Inspector with the backing filing chunk.

### 3. `cagr-trend-badge.tsx`
Dual-channel indicator:
* Combines geometric glyph (`↑`, `↓`, `→`, `~`), Lucide icon, text label (`Consistent Increase`, `Consistent Decrease`, `Flat`, `Volatile`), and CAGR percentage.
* Accessible without relying solely on color.

### 4. `ratio-table.tsx`
Dense, multi-period financial ratio table:
* Columns: Metric / Ratio, dynamic fiscal periods sorted ascending (e.g. FY2024, FY2025), Trend, and Evidence.
* Tabular figure alignment, negative number handling, and evidence actions per ratio row.
* Horizontally scrollable container on narrow viewports.

### 5. `finding-list.tsx`
Main presentation container:
* Displays Key Metrics in a responsive grid.
* Displays Multi-Period Ratios & Margins in `RatioTable`.
* Displays Growth Dynamics & CAGR in a compact summary.
* Graceful empty handling (renders nothing if `findings` is empty).

---

## 3. Evidence Provenance & Citation Drawer Integration

Financial findings preserve full provenance traceability:
* Every card and table row with `source_chunk_ids` includes an interactive **Evidence** action.
* Clicking **Evidence** invokes `useUiStore.getState().openCitationDrawer(chunkId)`.
* This activates the existing Phase 11.5 `CitationDrawer`, lazy-fetching the exact chunk text or Markdown table and displaying document metadata, page numbers, and similarity relevance.
* No duplicate citation systems or secondary drawers were created.

---

## 4. Verification & Testing

### Backend (`pytest`)
* `test_31_conversation_query_response_with_findings`: Verifies findings, metrics, periods, values, units, calculations, and chunk IDs are returned in `ConversationQueryResponse`.
* `test_32_conversation_query_response_empty_findings`: Verifies graceful fallback to `findings: []` when no findings exist.
* `test_chunk_endpoint.py`: All 5 tests passed.

### Frontend (`vitest` + RTL + MSW)
Created `frontend/tests/financial-findings.test.tsx` covering:
* Currency formatting ($B, $M, $K, negative parenthetical notation).
* Percentage, ratio, and share formatting.
* Metric name institutional title mapping.
* Period formatting (single year, YoY comparison, multi-year span).
* Authoritative trend parsing (improving, declining, volatile).
* MetricCard rendering with value, period, YoY change, and missing field handling.
* RatioTable multi-period rendering and row alignment.
* Dual-channel CagrTrendBadge glyphs and text labels.
* FindingList grouping into metrics, ratios, and growth.
* Evidence button interaction verifying chunk ID forwarding to `CitationDrawer`.

### Verification Suite Results
* **Backend Pytest**: 7 passed (100%)
* **Frontend Vitest**: 96 passed across 8 test files (100%)
* **TypeScript Typecheck**: 0 errors (`tsc --noEmit`)
* **ESLint**: 0 warnings or errors (`next lint`)
* **Production Build**: 0 errors (`next build`, all 8 routes static prerendered)
