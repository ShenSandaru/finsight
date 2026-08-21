# Multi-Period Sequencing & Deterministic CAGR Trend Analysis (Sprint 10.2)

## 1. Overview & Objectives

Sprint 10.2 extends the **Financial Analyzer Agent Node** (`backend/app/agents/financial_analyzer.py`) to support multi-year financial time-series analysis. It introduces:
1. **Multi-Period Chronological Sequencing** across $\ge 2$ annual periods.
2. **Sequential YoY Growth** across all adjacent period pairs ($t_{i-1} \to t_i$).
3. **Compound Annual Growth Rate (CAGR)** calculated deterministically over elapsed years ($N$).
4. **Deterministic Trend Classification** across $\ge 3$ periods.

All mathematical computations are executed purely in Python with zero added LLM calls.

---

## 2. Period Normalization & Annual Filtering

- **Format**: Strictly filters for 4-digit numeric annual periods (`"2022"`, `"2023"`, `"2024"`, `"2025"`).
- **Exclusion of Non-Annual Tokens**: Quarterly tokens (e.g. `Q1`, `Q2`, `Q3`, `2024-Q3`) are omitted from annual CAGR computations to avoid horizon mismatch.
- **Chronological Ordering**: Converts string year tokens to integer years, sorting them in ascending chronological order before analysis.

---

## 3. Mathematical Formulations & Rules

### A. Sequential YoY Growth
For every adjacent chronological pair $(p_{i-1}, p_i)$:
$$\text{Growth} = \left( \frac{V_i - V_{i-1}}{|V_{i-1}|} \right) \times 100$$
- If $V_{i-1} = 0$, the calculation is skipped to avoid division by zero.
- Preserves negative-to-positive and positive-to-negative delta semantics.

### B. Compound Annual Growth Rate (CAGR)
For multi-year annual series where $V_{\text{start}} > 0$ and $V_{\text{end}} > 0$:
$$\text{CAGR} = \left( \left( \frac{V_{\text{end}}}{V_{\text{start}}} \right)^{\frac{1}{N}} - 1 \right) \times 100$$
where:
$$N = \text{Ending Year} - \text{Beginning Year} \quad (\text{Elapsed calendar/fiscal years})$$

#### CAGR Edge Cases:
- **$V_{\text{start}} \le 0$ or $V_{\text{end}} < 0$**: Omitted (financially invalid / outside real root domain).
- **$V_{\text{start}} > 0$ and $V_{\text{end}} = 0$**: Returns `-100.0%`.
- **Missing Intermediate Years**: $N$ remains the true elapsed year span, with an explicit audit note: `(Incomplete Series with missing intermediate periods)`.

### C. Deterministic Trend Direction Classification
Evaluated across $\ge 3$ chronological points:
- **`Consistent Increase`**: $V_i > V_{i-1}$ for all $i$.
- **`Consistent Decrease`**: $V_i < V_{i-1}$ for all $i$.
- **`Flat`**: $|V_i - V_0| \le 0.005 \times |V_0|$ for all $i$ (or all zeros).
- **`Volatile`**: Contains mixed positive and negative deltas.
- **`Incomplete Series`**: Appended if intermediate fiscal years are missing from the retrieved sequence.

---

## 4. Multi-Period Provenance

Every derived finding (`{metric}_growth`, `{metric}_cagr`, `{metric}_trend`) aggregates the `source_chunk_ids` across all component periods:
$$\text{source\_chunk\_ids} = \bigcup_{p \in \text{series}} \text{finding}(p).\text{source\_chunk\_ids}$$

Ensures seamless audit passing in `CitationAuditorNode` and strict validation in `ResponseGuard`.

---

## 5. Verification Results

- **Unit & Integration Suite**: **227 passed, 0 failed** in `pytest`.
- **Targeted Trend Tests**:
  - `test_05d_multi_period_cagr_and_sequential_yoy` (chronological ordering, sequential YoY, 3-year CAGR, multi-chunk provenance).
  - `test_05e_cagr_missing_intermediate_years_and_edge_cases` (missing intermediate years with true $N=5$ elapsed years).
  - `test_05f_trend_classifications_decrease_flat_volatile` (Consistent Decrease, Flat, and Volatile trends).
- **Docker E2E Suite**: **E2E 1 through E2E 11 passed** in container environment (`backend/tests/e2e_test.py`).
- **Dependencies**: `pip check` clean (**No broken requirements found**).
