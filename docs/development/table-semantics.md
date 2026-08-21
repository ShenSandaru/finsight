# Financial Table Semantics & Classification Architecture (Sprint 4.2) — FinSight

This document details the architecture, data contracts, classification heuristics, period detection, and metric normalization mechanisms for FinSight's PDF financial table semantics pipeline.

---

## 1. Architectural Overview & Design Philosophy

Sprint 4.2 introduces `FinancialTableSemanticService` in `app/services/table_semantics.py` to enrich `ExtractedTable` objects with high-level financial metadata without external LLM calls or database persistence.

### Key Architectural Invariants
1. **Deterministic & Explainable:** Classification uses a multi-signal heuristic algorithm (titles, row labels, headers, and context) with explicit confidence scores and evidence breakdowns.
2. **Conservative Classification:** If evidence is weak (confidence score $< 0.40$) or ambiguous (margin between top two candidates $< 0.10$), `statement_type` defaults to `"unknown"`.
3. **In-Memory Enrichment:** `ExtractedTable` instances are enriched via `table.semantics = FinancialTableSemantics(...)`. Zero database `Chunk` records or schema migrations are created.
4. **No LLM / Vector Dependencies:** Completely standalone, fast, and testable without external network calls or vector indexing.

---

## 2. In-Memory Data Contract: `FinancialTableSemantics`

Defined in `app/services/table_semantics.py`:

```python
@dataclass
class FinancialTableSemantics:
    statement_type: str                  # Income Statement, Balance Sheet, Cash Flow, etc.
    confidence: float                    # Heuristic score bounded [0.0, 1.0]
    period_type: str                     # Annual, Quarterly, Year-to-Date, Point-in-Time, Unknown
    fiscal_periods: list[str]            # Extracted 4-digit years (e.g. ["2025", "2024"])
    period_context: str | None           # Original phrase (e.g. "Years Ended December 31, 2025")
    currency: str | None                 # Reused explicit currency ISO code (e.g. "USD")
    units: str | None                    # Reused explicit unit scale (e.g. "millions")
    has_year_columns: bool               # True if 4-digit years found in headers
    has_quarter_columns: bool            # True if Q1/Q2/Q3/Q4 found in headers
    has_ttm_period: bool                 # True if TTM / trailing 12 months detected
    key_metrics: list[str]               # Standardized row metric IDs (e.g. ["revenue", "net_income"])
    evidence: dict[str, Any]             # Explainable score components & matched terms
```

### Supported Statement Types
- `income_statement`: Consolidated Statements of Operations / Earnings / Income
- `balance_sheet`: Consolidated Balance Sheets / Statements of Financial Position
- `cash_flow`: Consolidated Statements of Cash Flows
- `stockholders_equity`: Statements of Stockholders' Equity / Shareholders' Equity
- `comprehensive_income`: Statements of Comprehensive Income
- `segment_information`: Segment Revenue / Segment Reporting
- `revenue_breakdown`: Disaggregated Revenue / Product Revenue
- `debt`: Long-Term Debt / Senior Notes / Borrowings
- `other_financial`: Generic financial tables not matching major statement types
- `unknown`: Ambiguous or unclassified non-financial tables

---

## 3. Heuristic Classification Algorithm

### A. Title Evidence (Weight: 0.50 - 0.60)
Scans `table.title` against high-confidence regex patterns (e.g., `Consolidated Statements of Operations` $\rightarrow$ `income_statement`). First matching title pattern takes precedence.

### B. Row Label Evidence (Weight: 0.10 - 0.20 per match, capped at 0.50)
Scans column 0 row labels against weighted dictionaries of financial terms:
- **Income Statement:** `revenue`, `gross profit`, `operating income`, `net income`, `earnings per share`.
- **Balance Sheet:** `cash and cash equivalents`, `total assets`, `total liabilities`, `retained earnings`, `stockholders' equity`.
- **Cash Flow:** `operating activities`, `investing activities`, `financing activities`, `capital expenditures`.
- **Stockholders' Equity:** `common stock`, `additional paid-in capital`, `treasury stock`, `dividends declared`.

### C. Confidence & Ambiguity Margin Decision
1. **Threshold Check:** If top candidate score $< 0.40$, `statement_type = "unknown"`.
2. **Ambiguity Margin Check:** If `(top_score - second_score) < 0.10` and `second_score >= 0.40`, `statement_type = "unknown"` due to ambiguity.

---

## 4. Period & Metric Extraction

### Fiscal Period & Type Detection
- **Years:** Extracts 4-digit years (`2020`-`2035`) from headers and titles.
- **Context:** Extracts explicit phrases like `"Years Ended December 31"`, `"Three Months Ended March 31"`, `"As of December 31"`.
- **Period Types:**
  - `annual`: `"Years Ended"` or year columns without quarters.
  - `quarterly`: `"Three Months Ended"` or `Q1`-`Q4` headers.
  - `year_to_date`: `"Six Months Ended"` or `"Nine Months Ended"`.
  - `point_in_time`: `"As of"` or `"Balance Sheet"` date snapshots.

### Metric Label Normalization
Map first-column row labels into normalized snake_case identifiers (e.g. `"Net Income"` $\rightarrow$ `"net_income"`, `"Total Assets"` $\rightarrow$ `"total_assets"`), leaving underlying raw cell strings untouched in `ExtractedTable.rows`.

---

## 5. Scope & Deferred Features

The following features remain intentionally **NOT** implemented in Sprint 4.2:
- ❌ **Database Storage:** Tables are not saved as `Chunk` DB rows.
- ❌ **LLM / OpenAI Integration:** Classification does not call external APIs.
- ❌ **Vector Search & RAG:** Embeddings and vector indices are deferred to later phases.
