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
    def extract_metrics_from_text(cls, content: str, chunk_id: UUID) -> list[FinancialFinding]:
        """
        Extract numerical financial figures from table or text chunk content.
        Looks for standard financial rows like Revenue, Gross Profit, Net Income, Operating Cash Flow.
        """
        findings: list[FinancialFinding] = []
        lines = content.split("\n")

        current_periods: list[str] = []
        for line in lines:
            # Check for header period definitions (e.g. 2025, 2024)
            found_periods = re.findall(r"\b(20\d\d|19\d\d)\b", line)
            if len(found_periods) >= 2 and not current_periods:
                current_periods = found_periods

            # Check for metric rows
            lower_line = line.lower()
            metric_name = None
            if "total revenue" in lower_line or "net sales" in lower_line or "revenue" in lower_line:
                metric_name = "revenue"
            elif "gross profit" in lower_line or "gross margin" in lower_line:
                metric_name = "gross_profit"
            elif "net income" in lower_line or "net earnings" in lower_line:
                metric_name = "net_income"
            elif "operating cash flow" in lower_line or "operating activities" in lower_line:
                metric_name = "operating_cash_flow"
            elif "total assets" in lower_line:
                metric_name = "total_assets"
            elif "total liabilities" in lower_line:
                metric_name = "total_liabilities"

            if metric_name:
                # Extract numeric values with dollar signs or numbers
                # e.g., "$1,000", "1000", "$900"
                num_matches = re.findall(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", line)
                clean_numbers = [float(n.replace(",", "")) for n in num_matches if n.replace(",", "").replace(".", "").isdigit()]

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
                                    source_chunk_ids=[chunk_id],
                                )
                            )
                    else:
                        # Single period or default
                        period_found = found_periods[0] if found_periods else "latest"
                        findings.append(
                            FinancialFinding(
                                metric=metric_name,
                                period=period_found,
                                value=clean_numbers[0],
                                unit="$",
                                source_chunk_ids=[chunk_id],
                            )
                        )

        return findings

    @classmethod
    def compute_ratios_and_growth(cls, findings: list[FinancialFinding]) -> list[FinancialFinding]:
        """
        Deterministically compute Gross Margin, Net Margin, and YoY Growth rates using Python arithmetic.
        """
        derived_findings: list[FinancialFinding] = []
        by_period: dict[str, dict[str, FinancialFinding]] = {}

        for f in findings:
            if f.period not in by_period:
                by_period[f.period] = {}
            # Prefer first extracted finding per metric per period
            if f.metric not in by_period[f.period]:
                by_period[f.period][f.metric] = f

        # 1. Compute Margin Ratios per period
        for period, metrics in by_period.items():
            rev = metrics.get("revenue")
            gp = metrics.get("gross_profit")
            ni = metrics.get("net_income")

            if rev and gp and rev.value > 0:
                gross_margin = round((gp.value / rev.value) * 100, 2)
                sources = list(set(rev.source_chunk_ids + gp.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="gross_margin",
                        period=period,
                        value=gross_margin,
                        unit="%",
                        source_chunk_ids=sources,
                        calculation=f"({gp.value} / {rev.value}) * 100",
                    )
                )

            if rev and ni and rev.value > 0:
                net_margin = round((ni.value / rev.value) * 100, 2)
                sources = list(set(rev.source_chunk_ids + ni.source_chunk_ids))
                derived_findings.append(
                    FinancialFinding(
                        metric="net_margin",
                        period=period,
                        value=net_margin,
                        unit="%",
                        source_chunk_ids=sources,
                        calculation=f"({ni.value} / {rev.value}) * 100",
                    )
                )

        # 2. Compute YoY Growth between pairs of years
        sorted_periods = sorted([p for p in by_period.keys() if p.isdigit()], reverse=True)
        if len(sorted_periods) >= 2:
            curr_p, prev_p = sorted_periods[0], sorted_periods[1]
            curr_metrics = by_period[curr_p]
            prev_metrics = by_period[prev_p]

            for m in ("revenue", "gross_profit", "net_income"):
                if m in curr_metrics and m in prev_metrics and prev_metrics[m].value > 0:
                    val_curr = curr_metrics[m].value
                    val_prev = prev_metrics[m].value
                    growth = round(((val_curr - val_prev) / val_prev) * 100, 2)
                    sources = list(set(curr_metrics[m].source_chunk_ids + prev_metrics[m].source_chunk_ids))
                    derived_findings.append(
                        FinancialFinding(
                            metric=f"{m}_growth",
                            period=f"{curr_p}_vs_{prev_p}",
                            value=growth,
                            unit="%",
                            source_chunk_ids=sources,
                            calculation=f"(({val_curr} - {val_prev}) / {val_prev}) * 100",
                        )
                    )

        return derived_findings

    @classmethod
    async def analyze(cls, state: ResearchState) -> dict[str, Any]:
        """
        Execute financial analysis node.
        """
        chunks = state.get("retrieved_chunks", [])
        logger.info("Financial Analyzer Node processing %d retrieved chunks", len(chunks))

        raw_findings: list[FinancialFinding] = []
        for chunk in chunks:
            extracted = cls.extract_metrics_from_text(chunk.content, chunk.chunk_id)
            raw_findings.extend(extracted)

        derived = cls.compute_ratios_and_growth(raw_findings)
        all_findings = raw_findings + derived

        logger.info("Financial Analyzer Node produced %d findings (%d raw, %d derived)", len(all_findings), len(raw_findings), len(derived))

        return {
            "findings": all_findings,
            "step_count": state.get("step_count", 0) + 1,
            "status": "analyzed",
        }
