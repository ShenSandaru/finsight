# Extended Financial Metrics & Ratio Library (Sprint 10.1)

## 1. Overview & Objectives

Sprint 10.1 enhances the **Financial Analyzer Agent Node** (`backend/app/agents/financial_analyzer.py`) by extending deterministic financial extraction and ratio arithmetic in Python. All numerical calculations are strictly executed in application code prior to synthesis to completely eliminate LLM arithmetic hallucinations.

---

## 2. Supported Financial Metrics & Formulas

| Metric | Category | Canonical Key | Deterministic Formula | Unit | Raw Line Items Required |
|---|---|---|---|---|---|
| **Gross Margin** | Margin | `gross_margin` | `(gross_profit / revenue) * 100` | `%` | `gross_profit`, `revenue` |
| **Operating Margin** | Margin | `operating_margin` | `(operating_income / revenue) * 100` | `%` | `operating_income`, `revenue` |
| **Net Margin** | Margin | `net_margin` | `(net_income / revenue) * 100` | `%` | `net_income`, `revenue` |
| **Return on Assets (ROA)** | Profitability | `roa` | `(net_income / total_assets) * 100` | `%` | `net_income`, `total_assets` |
| **Current Ratio** | Liquidity | `current_ratio` | `total_current_assets / total_current_liabilities` | `ratio` | `total_current_assets`, `total_current_liabilities` |
| **Debt-to-Equity** | Solvency | `debt_to_equity` | `total_liabilities / total_stockholders_equity` | `ratio` | `total_liabilities`, `total_stockholders_equity` |
| **Free Cash Flow (FCF)** | Cash Flow | `free_cash_flow` | `operating_cash_flow - abs(capital_expenditures)` | `$` | `operating_cash_flow`, `capital_expenditures` |
| **YoY Growth** | Growth | `{metric}_growth` | `((val_curr - val_prev) / abs(val_prev)) * 100` | `%` | Any period metric pair ($t_0, t_1$) |

---

## 3. Provenance & Edge Case Safety

- **Multi-Chunk Provenance**: Every calculated metric merges the `source_chunk_ids` of both numerator and denominator records (`source_chunk_ids = list(set(num.source_chunk_ids + den.source_chunk_ids))`).
- **Zero Division & Missing Denominators**: Guarded against `0` and missing values (`den.value != 0`); metrics with missing inputs are cleanly omitted without raising exceptions.
- **Negative Values & Bracketed Accounting Numbers**: Supports parenthesized values `$(400)` and negative cash flows. Free Cash Flow automatically handles CapEx whether recorded as positive outflows or bracketed negative accounting entries via `abs(capex.value)`.
- **Zero LLM Arithmetic Calls**: 100% deterministic Python calculation.

---

## 4. Verification & Test Metrics

- **Unit & Integration Suite**: **224 passed, 0 failed** in `pytest`.
- **Targeted Extended Ratio Tests**: Verified in `backend/tests/test_agent_system.py` (`test_05b_extended_financial_metrics_calculations`, `test_05c_edge_cases_zero_division_and_negative_values`).
- **Docker E2E Suite**: **E2E 1 through E2E 10 passed** in container environment (`backend/tests/e2e_test.py`).
- **Dependencies**: `pip check` confirmed clean with no broken requirements.
