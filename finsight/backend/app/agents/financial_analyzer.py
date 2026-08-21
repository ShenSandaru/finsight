"""Financial Analyzer Agent Node for FinSight Multi-Agent Research System (Sprint 9.1)."""

import logging
import re
from typing import Any
from uuid import UUID

from app.agents.state import ResearchState, FinancialFinding, FinancialAnalysis

logger = logging.getLogger("finsight.agents.financial_analyzer")


class FinancialAnalyzerNode:
    """
    Extracts structured financial metrics and calculates deterministic ratios from retrieved document chunks.
    Performs arithmetic calculations in Python to guarantee numerical accuracy.
    """

    @classmethod
    def extract_metrics_from_text(cls, content: str, chunk_id: UUID, document_id: UUID | None = None) -> list[FinancialFinding]:
        """
        Extract numerical financial figures from table or text chunk content.
        Looks for standard financial rows like Revenue, Gross Profit, Net Income, Operating Cash Flow.
        Associates each finding with its owning document_id.
        """
        findings: list[FinancialFinding] = []
        lines = content.split("\n")

        current_periods: list[str] = []
        # First scan entire chunk text for header periods or year mentions
        all_text_periods = re.findall(r"\b(20\d\d|19\d\d)\b", content)
        default_period = all_text_periods[0] if all_text_periods else "latest"

        for line in lines:
            # Check for header period definitions (e.g. 2025, 2024)
            found_periods = re.findall(r"\b(20\d\d|19\d\d)\b", line)
            if len(found_periods) >= 2 and not current_periods:
                current_periods = found_periods
            elif len(found_periods) == 1 and not current_periods:
                current_periods = [found_periods[0]]

            # Check for metric rows
            lower_line = line.lower()
            metric_name = None
            if "operating income" in lower_line or "operating profit" in lower_line:
                metric_name = "operating_income"
            elif "total revenue" in lower_line or "net sales" in lower_line or "revenue" in lower_line:
                metric_name = "revenue"
            elif "gross profit" in lower_line or "gross margin" in lower_line:
                metric_name = "gross_profit"
            elif "net income" in lower_line or "net earnings" in lower_line:
                metric_name = "net_income"
            elif "capital expenditures" in lower_line or "additions to property" in lower_line or "capex" in lower_line:
                metric_name = "capital_expenditures"
            elif "operating cash flow" in lower_line or "operating activities" in lower_line:
                metric_name = "operating_cash_flow"
            elif "total current assets" in lower_line:
                metric_name = "total_current_assets"
            elif "total current liabilities" in lower_line:
                metric_name = "total_current_liabilities"
            elif "total assets" in lower_line:
                metric_name = "total_assets"
            elif "total stockholders' equity" in lower_line or "total shareholders' equity" in lower_line or "stockholders' equity" in lower_line or "shareholders' equity" in lower_line:
                metric_name = "total_stockholders_equity"
            elif "total liabilities" in lower_line:
                metric_name = "total_liabilities"

            if metric_name:
                # Extract numeric values with dollar signs, parentheses (negative values), or numbers
                num_matches = re.findall(r"(?:-|\$?\s*\()?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*\)?", line)
                raw_tokens = re.findall(r"(\(?\$?\s*-?[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?\s*\)?)", line)

                clean_numbers: list[float] = []
                for token in raw_tokens:
                    cleaned = token.replace("$", "").replace(",", "").strip()
                    if not cleaned:
                        continue
                    is_neg = ("(" in token and ")" in token) or "-" in token
                    digit_part = cleaned.replace("(", "").replace(")", "").replace("-", "")
                    try:
                        val = float(digit_part)
                        if is_neg:
                            val = -val
                        clean_numbers.append(val)
                    except ValueError:
                        continue

                # Map extracted numbers to periods
                if clean_numbers:
                    if current_periods and len(clean_numbers) >= len(current_periods):
                        for p, val in zip(current_periods, clean_numbers):
                            findings.append(
                                FinancialFinding(
                                    metric=metric_name,
                                    period=p,
                                    value=val,
                                    unit="$",
                                    document_id=document_id,
                                    source_chunk_ids=[chunk_id],
                                )
                            )
                    else:
                        # Single period or default
                        period_found = found_periods[0] if found_periods else (current_periods[0] if current_periods else default_period)
                        findings.append(
                            FinancialFinding(
                                metric=metric_name,
                                period=period_found,
                                value=clean_numbers[0],
                                unit="$",
                                document_id=document_id,
                                source_chunk_ids=[chunk_id],
                            )
                        )

        return findings

    @classmethod
    def compute_ratios_and_growth_for_doc(cls, findings: list[FinancialFinding], doc_id: UUID | None) -> list[FinancialFinding]:
        """
        Deterministically compute single-document financial ratios, YoY, CAGR, and Trend Direction.
        """
        derived_findings: list[FinancialFinding] = []
        by_period: dict[str, dict[str, FinancialFinding]] = {}

        for f in findings:
            if f.period not in by_period:
                by_period[f.period] = {}
            if f.metric not in by_period[f.period]:
                by_period[f.period][f.metric] = f

        # 1. Compute Financial Ratios per period
        for period, metrics in by_period.items():
            rev = metrics.get("revenue")
            gp = metrics.get("gross_profit")
            op_inc = metrics.get("operating_income")
            ni = metrics.get("net_income")
            assets = metrics.get("total_assets")
            curr_assets = metrics.get("total_current_assets")
            curr_liab = metrics.get("total_current_liabilities")
            liab = metrics.get("total_liabilities")
            equity = metrics.get("total_stockholders_equity")
            ocf = metrics.get("operating_cash_flow")
            capex = metrics.get("capital_expenditures")

            # A. Gross Margin (%)
            if rev and gp and rev.value != 0:
                gross_margin = round((gp.value / rev.value) * 100, 2)
                sources = list(set(rev.source_chunk_ids + gp.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="gross_margin",
                        period=period,
                        value=gross_margin,
                        unit="%",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"({gp.value} / {rev.value}) * 100",
                    )
                )

            # B. Operating Margin (%)
            if rev and op_inc and rev.value != 0:
                operating_margin = round((op_inc.value / rev.value) * 100, 2)
                sources = list(set(rev.source_chunk_ids + op_inc.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="operating_margin",
                        period=period,
                        value=operating_margin,
                        unit="%",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"({op_inc.value} / {rev.value}) * 100",
                    )
                )

            # C. Net Margin (%)
            if rev and ni and rev.value != 0:
                net_margin = round((ni.value / rev.value) * 100, 2)
                sources = list(set(rev.source_chunk_ids + ni.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="net_margin",
                        period=period,
                        value=net_margin,
                        unit="%",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"({ni.value} / {rev.value}) * 100",
                    )
                )

            # D. Return on Assets / ROA (%)
            if ni and assets and assets.value != 0:
                roa = round((ni.value / assets.value) * 100, 2)
                sources = list(set(ni.source_chunk_ids + assets.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="roa",
                        period=period,
                        value=roa,
                        unit="%",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"({ni.value} / {assets.value}) * 100",
                    )
                )

            # E. Current Ratio (ratio)
            if curr_assets and curr_liab and curr_liab.value != 0:
                current_ratio = round(curr_assets.value / curr_liab.value, 2)
                sources = list(set(curr_assets.source_chunk_ids + curr_liab.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="current_ratio",
                        period=period,
                        value=current_ratio,
                        unit="ratio",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"{curr_assets.value} / {curr_liab.value}",
                    )
                )

            # F. Debt-to-Equity (ratio)
            if liab and equity and equity.value != 0:
                debt_to_equity = round(liab.value / equity.value, 2)
                sources = list(set(liab.source_chunk_ids + equity.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="debt_to_equity",
                        period=period,
                        value=debt_to_equity,
                        unit="ratio",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"{liab.value} / {equity.value}",
                    )
                )

            # G. Free Cash Flow (FCF) ($)
            if ocf and capex:
                capex_abs = abs(capex.value)
                fcf = round(ocf.value - capex_abs, 2)
                sources = list(set(ocf.source_chunk_ids + capex.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="free_cash_flow",
                        period=period,
                        value=fcf,
                        unit="$",
                        document_id=doc_id,
                        source_chunk_ids=sources,
                        calculation=f"{ocf.value} - {capex_abs}",
                    )
                )

        # 2. Multi-Period Sequencing, Sequential YoY, CAGR, and Trend Direction
        annual_periods = sorted([int(p) for p in by_period.keys() if p.isdigit() and len(p) == 4])

        if len(annual_periods) >= 2:
            metric_series: dict[str, list[tuple[int, float, list[UUID]]]] = {}
            for yr in annual_periods:
                yr_str = str(yr)
                for metric_name, finding in by_period[yr_str].items():
                    if metric_name not in metric_series:
                        metric_series[metric_name] = []
                    metric_series[metric_name].append((yr, finding.value, finding.source_chunk_ids))

            for metric_name, series in metric_series.items():
                # A. Sequential YoY Growth between every adjacent pair of available years
                for i in range(1, len(series)):
                    prev_yr, val_prev, prev_ids = series[i - 1]
                    curr_yr, val_curr, curr_ids = series[i]

                    if val_prev != 0:
                        growth = round(((val_curr - val_prev) / abs(val_prev)) * 100, 2)
                        pair_sources = list(set(prev_ids + curr_ids))
                        derived_findings.append(
                            FinancialFinding(
                                metric=f"{metric_name}_growth",
                                period=f"{curr_yr}_vs_{prev_yr}",
                                value=growth,
                                unit="%",
                                document_id=doc_id,
                                source_chunk_ids=pair_sources,
                                calculation=f"(({val_curr} - {val_prev}) / {abs(val_prev)}) * 100",
                            )
                        )

                # B. Multi-Period CAGR
                first_yr, val_start, first_ids = series[0]
                last_yr, val_end, last_ids = series[-1]
                elapsed_years = last_yr - first_yr

                if elapsed_years >= 1:
                    all_series_sources = list(set(cid for _, _, ids in series for cid in ids))
                    
                    if val_start > 0 and val_end > 0:
                        cagr = round((((val_end / val_start) ** (1.0 / elapsed_years)) - 1.0) * 100, 2)
                        missing_intermediate = (len(series) - 1) < elapsed_years
                        calc_note = f"(({val_end} / {val_start}) ^ (1 / {elapsed_years}) - 1) * 100"
                        if missing_intermediate:
                            calc_note += " (Incomplete Series with missing intermediate periods)"
                        
                        derived_findings.append(
                            FinancialFinding(
                                metric=f"{metric_name}_cagr",
                                period=f"{first_yr}_to_{last_yr}",
                                value=cagr,
                                unit="%",
                                document_id=doc_id,
                                source_chunk_ids=all_series_sources,
                                calculation=calc_note,
                            )
                        )
                    elif val_start > 0 and val_end == 0:
                        derived_findings.append(
                            FinancialFinding(
                                metric=f"{metric_name}_cagr",
                                period=f"{first_yr}_to_{last_yr}",
                                value=-100.0,
                                unit="%",
                                document_id=doc_id,
                                source_chunk_ids=all_series_sources,
                                calculation=f"(({val_end} / {val_start}) ^ (1 / {elapsed_years}) - 1) * 100",
                            )
                        )

                # C. Deterministic Trend Direction Classification
                if len(series) >= 3:
                    values = [v for _, v, _ in series]
                    all_series_sources = list(set(cid for _, _, ids in series for cid in ids))
                    missing_intermediate = (len(series) - 1) < elapsed_years

                    is_inc = all(values[k] > values[k - 1] for k in range(1, len(values)))
                    is_dec = all(values[k] < values[k - 1] for k in range(1, len(values)))
                    is_flat = all(abs(values[k] - values[0]) <= (0.005 * abs(values[0])) for k in range(1, len(values))) if values[0] != 0 else all(v == 0 for v in values)

                    if is_inc:
                        trend_label = "Consistent Increase"
                    elif is_dec:
                        trend_label = "Consistent Decrease"
                    elif is_flat:
                        trend_label = "Flat"
                    else:
                        trend_label = "Volatile"

                    if missing_intermediate:
                        trend_label += " (Incomplete Series)"

                    val_sequence_str = " -> ".join([str(v) for v in values])
                    derived_findings.append(
                        FinancialFinding(
                            metric=f"{metric_name}_trend",
                            period=f"{first_yr}_to_{last_yr}",
                            value=1.0 if is_inc else (-1.0 if is_dec else 0.0),
                            unit="trend",
                            document_id=doc_id,
                            source_chunk_ids=all_series_sources,
                            calculation=f"{trend_label}: [{val_sequence_str}]",
                        )
                    )

        return derived_findings

    @classmethod
    def compute_cross_document_comparisons(cls, all_findings: list[FinancialFinding]) -> list[FinancialFinding]:
        """
        Deterministically compare findings across different document_ids for the same (metric, period).
        Generates absolute difference and percentage difference findings with merged source provenance.
        """
        comparisons: list[FinancialFinding] = []
        # Group findings by (metric, period) across distinct document_ids
        by_metric_period: dict[tuple[str, str], dict[UUID, FinancialFinding]] = {}

        for f in all_findings:
            # Skip existing comparisons or trend findings
            if "_comparison" in f.metric or f.unit == "trend" or f.document_id is None:
                continue
            key = (f.metric, f.period)
            if key not in by_metric_period:
                by_metric_period[key] = {}
            if f.document_id not in by_metric_period[key]:
                by_metric_period[key][f.document_id] = f

        for (metric_name, period), doc_map in by_metric_period.items():
            doc_ids = sorted(list(doc_map.keys()), key=lambda d: str(d))
            if len(doc_ids) >= 2:
                # Compare each pair of documents: Doc B vs Doc A
                for i in range(len(doc_ids)):
                    for j in range(i + 1, len(doc_ids)):
                        doc_a_id = doc_ids[i]
                        doc_b_id = doc_ids[j]
                        f_a = doc_map[doc_a_id]
                        f_b = doc_map[doc_b_id]

                        val_a = f_a.value
                        val_b = f_b.value
                        merged_sources = list(set(f_a.source_chunk_ids + f_b.source_chunk_ids))

                        # 1. Absolute Difference: B - A
                        abs_diff = round(val_b - val_a, 2)
                        comparisons.append(
                            FinancialFinding(
                                metric=f"{metric_name}_absolute_difference",
                                period=f"{period}_docB_vs_docA",
                                value=abs_diff,
                                unit=f_a.unit,
                                source_chunk_ids=merged_sources,
                                calculation=f"{val_b} - {val_a} [DocB ({str(doc_b_id)[:8]}) vs DocA ({str(doc_a_id)[:8]})]",
                            )
                        )

                        # 2. Percentage Difference: ((B - A) / abs(A)) * 100
                        if val_a != 0:
                            pct_diff = round(((val_b - val_a) / abs(val_a)) * 100, 2)
                            comparisons.append(
                                FinancialFinding(
                                    metric=f"{metric_name}_comparison",
                                    period=f"{period}_docB_vs_docA",
                                    value=pct_diff,
                                    unit="%",
                                    source_chunk_ids=merged_sources,
                                    calculation=f"(({val_b} - {val_a}) / {abs(val_a)}) * 100 [DocB vs DocA]",
                                )
                            )

        return comparisons

    @classmethod
    def compute_ratios_and_growth(cls, findings: list[FinancialFinding]) -> list[FinancialFinding]:
        """
        Group findings by document_id, calculate intra-document metrics, and then cross-document comparisons.
        """
        by_doc: dict[UUID | None, list[FinancialFinding]] = {}
        for f in findings:
            if f.document_id not in by_doc:
                by_doc[f.document_id] = []
            by_doc[f.document_id].append(f)

        derived_all: list[FinancialFinding] = []
        for doc_id, doc_findings in by_doc.items():
            doc_derived = cls.compute_ratios_and_growth_for_doc(doc_findings, doc_id)
            derived_all.extend(doc_derived)

        # Cross-document comparisons
        all_scoped_findings = findings + derived_all
        cross_doc_comparisons = cls.compute_cross_document_comparisons(all_scoped_findings)
        derived_all.extend(cross_doc_comparisons)

        return derived_all

    @classmethod
    async def analyze(cls, state: ResearchState) -> dict[str, Any]:
        """
        Execute financial analysis node.
        """
        chunks = state.get("retrieved_chunks", [])
        logger.info("Financial Analyzer Node processing %d retrieved chunks", len(chunks))

        raw_findings: list[FinancialFinding] = []
        for chunk in chunks:
            extracted = cls.extract_metrics_from_text(chunk.content, chunk.chunk_id, chunk.document_id)
            raw_findings.extend(extracted)

        derived = cls.compute_ratios_and_growth(raw_findings)
        all_findings = raw_findings + derived

        logger.info("Financial Analyzer Node produced %d findings (%d raw, %d derived)", len(all_findings), len(raw_findings), len(derived))

        return {
            "findings": all_findings,
            "step_count": state.get("step_count", 0) + 1,
            "status": "analyzed",
        }
