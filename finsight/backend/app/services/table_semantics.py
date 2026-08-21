"""Financial table semantic classification, period detection, and metric normalization service."""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.table_extractor import ExtractedTable

logger = logging.getLogger("finsight.services.table_semantics")


class StatementType:
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    STOCKHOLDERS_EQUITY = "stockholders_equity"
    COMPREHENSIVE_INCOME = "comprehensive_income"
    SEGMENT_INFORMATION = "segment_information"
    REVENUE_BREAKDOWN = "revenue_breakdown"
    DEBT = "debt"
    OTHER_FINANCIAL = "other_financial"
    UNKNOWN = "unknown"


class PeriodType:
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    YEAR_TO_DATE = "year_to_date"
    MONTHLY = "monthly"
    POINT_IN_TIME = "point_in_time"
    UNKNOWN = "unknown"


@dataclass
class FinancialTableSemantics:
    """Structured in-memory representation of financial table semantics."""

    statement_type: str = StatementType.UNKNOWN
    confidence: float = 0.0
    period_type: str = PeriodType.UNKNOWN
    fiscal_periods: list[str] = field(default_factory=list)
    period_context: str | None = None
    currency: str | None = None
    units: str | None = None
    has_year_columns: bool = False
    has_quarter_columns: bool = False
    has_ttm_period: bool = False
    key_metrics: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


class FinancialTableSemanticService:
    """Service for classifying financial statement types, extracting period semantics, and normalizing key metrics."""

    MIN_CONFIDENCE_THRESHOLD = 0.40
    SCORE_MARGIN_THRESHOLD = 0.10

    # Title detection rules: (pattern, statement_type, title_weight)
    TITLE_PATTERNS = [
        (re.compile(r"Consolidated\s+Statements?\s+of\s+(?:Operations|Income|Earnings)", re.IGNORECASE), StatementType.INCOME_STATEMENT, 0.60),
        (re.compile(r"Statements?\s+of\s+(?:Operations|Income|Earnings)", re.IGNORECASE), StatementType.INCOME_STATEMENT, 0.55),
        (re.compile(r"Income\s+Statements?", re.IGNORECASE), StatementType.INCOME_STATEMENT, 0.55),
        
        (re.compile(r"Consolidated\s+Balance\s+Sheets?", re.IGNORECASE), StatementType.BALANCE_SHEET, 0.60),
        (re.compile(r"Balance\s+Sheets?", re.IGNORECASE), StatementType.BALANCE_SHEET, 0.55),
        (re.compile(r"Statements?\s+of\s+Financial\s+Position", re.IGNORECASE), StatementType.BALANCE_SHEET, 0.55),
        
        (re.compile(r"Consolidated\s+Statements?\s+of\s+Cash\s+Flows?", re.IGNORECASE), StatementType.CASH_FLOW, 0.60),
        (re.compile(r"Statements?\s+of\s+Cash\s+Flows?", re.IGNORECASE), StatementType.CASH_FLOW, 0.55),
        (re.compile(r"Cash\s+Flows?", re.IGNORECASE), StatementType.CASH_FLOW, 0.50),

        (re.compile(r"Statements?\s+of\s+(?:Stockholders'|Shareholders'|Equity)", re.IGNORECASE), StatementType.STOCKHOLDERS_EQUITY, 0.60),
        (re.compile(r"(?:Stockholders'|Shareholders')\s+Equity", re.IGNORECASE), StatementType.STOCKHOLDERS_EQUITY, 0.55),

        (re.compile(r"Statements?\s+of\s+Comprehensive\s+Income", re.IGNORECASE), StatementType.COMPREHENSIVE_INCOME, 0.60),
        (re.compile(r"Comprehensive\s+Income", re.IGNORECASE), StatementType.COMPREHENSIVE_INCOME, 0.55),

        (re.compile(r"Segment\s+(?:Information|Reporting|Revenue)", re.IGNORECASE), StatementType.SEGMENT_INFORMATION, 0.55),
        (re.compile(r"Disaggregated\s+Revenue|Revenue\s+by\s+Product|Revenue\s+by\s+Region", re.IGNORECASE), StatementType.REVENUE_BREAKDOWN, 0.55),
        (re.compile(r"(?:Long-Term\s+)?Debt|Borrowings|Senior\s+Notes|Maturities\s+of\s+Debt", re.IGNORECASE), StatementType.DEBT, 0.55),
    ]

    # Weighted term dictionaries for first-column row labels
    ROW_TERM_WEIGHTS = {
        StatementType.INCOME_STATEMENT: {
            "revenue": 0.15,
            "total revenue": 0.18,
            "net sales": 0.15,
            "cost of sales": 0.12,
            "cost of revenue": 0.12,
            "cost of goods sold": 0.12,
            "gross profit": 0.15,
            "operating expenses": 0.10,
            "operating income": 0.15,
            "operating loss": 0.15,
            "net income": 0.20,
            "net earnings": 0.18,
            "earnings per share": 0.15,
            "diluted eps": 0.12,
            "provision for income taxes": 0.10,
        },
        StatementType.BALANCE_SHEET: {
            "cash and cash equivalents": 0.15,
            "accounts receivable": 0.12,
            "inventories": 0.10,
            "total current assets": 0.15,
            "total assets": 0.20,
            "accounts payable": 0.10,
            "total current liabilities": 0.15,
            "long-term debt": 0.12,
            "total liabilities": 0.18,
            "retained earnings": 0.12,
            "common stock": 0.10,
            "total stockholders' equity": 0.18,
            "total shareholders' equity": 0.18,
            "total liabilities and stockholders' equity": 0.20,
        },
        StatementType.CASH_FLOW: {
            "operating activities": 0.15,
            "net cash provided by operating activities": 0.20,
            "investing activities": 0.15,
            "net cash used in investing activities": 0.18,
            "financing activities": 0.15,
            "net cash provided by financing activities": 0.18,
            "capital expenditures": 0.12,
            "depreciation and amortization": 0.12,
            "cash and cash equivalents at beginning of period": 0.15,
            "cash and cash equivalents at end of period": 0.15,
        },
        StatementType.STOCKHOLDERS_EQUITY: {
            "common stock": 0.12,
            "additional paid-in capital": 0.15,
            "retained earnings": 0.12,
            "treasury stock": 0.15,
            "accumulated other comprehensive income": 0.12,
            "dividends declared": 0.12,
            "stock-based compensation": 0.10,
            "balance at beginning of period": 0.10,
            "balance at end of period": 0.10,
        },
        StatementType.COMPREHENSIVE_INCOME: {
            "other comprehensive income": 0.20,
            "foreign currency translation": 0.15,
            "unrealized gains": 0.15,
            "unrealized losses": 0.15,
            "total comprehensive income": 0.20,
            "comprehensive income": 0.18,
        },
        StatementType.DEBT: {
            "senior notes": 0.15,
            "term loans": 0.15,
            "revolving credit facility": 0.15,
            "commercial paper": 0.12,
            "principal amount": 0.12,
            "effective interest rate": 0.15,
            "maturities of debt": 0.18,
            "short-term borrowings": 0.15,
            "long-term debt": 0.15,
        },
        StatementType.REVENUE_BREAKDOWN: {
            "product revenue": 0.18,
            "service revenue": 0.18,
            "subscription revenue": 0.18,
            "disaggregated revenue": 0.20,
            "geographic region": 0.15,
        },
        StatementType.SEGMENT_INFORMATION: {
            "segment revenue": 0.20,
            "segment operating income": 0.20,
            "segment assets": 0.18,
            "intersegment revenue": 0.15,
        },
    }

    # Normalized metric mappings for column 0
    KNOWN_METRIC_MAP = {
        "revenue": "revenue",
        "total revenue": "revenue",
        "net sales": "revenue",
        "gross profit": "gross_profit",
        "gross margin": "gross_profit",
        "operating income": "operating_income",
        "operating profit": "operating_income",
        "operating loss": "operating_income",
        "net income": "net_income",
        "net earnings": "net_income",
        "earnings per share": "earnings_per_share",
        "diluted eps": "earnings_per_share",
        "total assets": "total_assets",
        "total current assets": "total_current_assets",
        "total liabilities": "total_liabilities",
        "total current liabilities": "total_current_liabilities",
        "cash and cash equivalents": "cash_and_cash_equivalents",
        "retained earnings": "retained_earnings",
        "total stockholders' equity": "total_stockholders_equity",
        "total shareholders' equity": "total_stockholders_equity",
        "net cash provided by operating activities": "operating_cash_flow",
        "operating cash flow": "operating_cash_flow",
        "capital expenditures": "capital_expenditures",
        "long-term debt": "long_term_debt",
    }

    def analyze_table(self, table: "ExtractedTable") -> FinancialTableSemantics:
        """
        Analyze an ExtractedTable to classify its statement type, period semantics, and metrics.
        """
        evidence: dict[str, Any] = {
            "title_matches": [],
            "row_matches": {},
            "header_matches": [],
            "score_components": {},
        }

        # Step 1: Score statement types using Title, Rows, and Headers
        scores: dict[str, float] = {st: 0.0 for st in [
            StatementType.INCOME_STATEMENT,
            StatementType.BALANCE_SHEET,
            StatementType.CASH_FLOW,
            StatementType.STOCKHOLDERS_EQUITY,
            StatementType.COMPREHENSIVE_INCOME,
            StatementType.SEGMENT_INFORMATION,
            StatementType.REVENUE_BREAKDOWN,
            StatementType.DEBT,
        ]}

        # A. Title evidence
        if table.title:
            for pattern, st_type, weight in self.TITLE_PATTERNS:
                if pattern.search(table.title):
                    scores[st_type] += weight
                    evidence["title_matches"].append({"title": table.title, "statement_type": st_type, "weight": weight})
                    break

        # B. Row label evidence (scanning first column values)
        row_labels = [row[0].lower() for row in table.rows if row and len(row) > 0]
        for st_type, term_dict in self.ROW_TERM_WEIGHTS.items():
            matched_terms = []
            st_row_score = 0.0
            for label in row_labels:
                for term, weight in term_dict.items():
                    if term in label:
                        st_row_score += weight
                        matched_terms.append(term)
            # Cap row score at 0.50
            st_row_score = min(0.50, st_row_score)
            if st_row_score > 0:
                scores[st_type] += st_row_score
                evidence["row_matches"][st_type] = {"matched_terms": matched_terms, "score": round(st_row_score, 3)}

        # C. Header evidence
        header_text = " ".join(table.headers).lower()
        if "as of" in header_text or "december 31" in header_text or "march 31" in header_text:
            if scores[StatementType.BALANCE_SHEET] > 0:
                scores[StatementType.BALANCE_SHEET] += 0.05
                evidence["header_matches"].append("balance_sheet_as_of_date")
        if "years ended" in header_text or "three months ended" in header_text:
            if scores[StatementType.INCOME_STATEMENT] > 0:
                scores[StatementType.INCOME_STATEMENT] += 0.05
                evidence["header_matches"].append("income_statement_period_header")

        # Step 2: Determine top candidates and apply conservative confidence thresholding
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_st, top_score = sorted_scores[0]
        second_st, second_score = sorted_scores[1]

        final_score = min(1.0, round(top_score, 3))
        evidence["score_components"] = {st: round(sc, 3) for st, sc in sorted_scores if sc > 0}
        evidence["top_score"] = final_score
        evidence["second_score"] = round(second_score, 3)

        # Classification decision logic
        if top_score < self.MIN_CONFIDENCE_THRESHOLD:
            statement_type = StatementType.UNKNOWN
            final_score = 0.0
            evidence["classification_reason"] = f"Top score ({top_score:.2f}) below threshold ({self.MIN_CONFIDENCE_THRESHOLD})"
        elif (top_score - second_score) < self.SCORE_MARGIN_THRESHOLD and second_score >= self.MIN_CONFIDENCE_THRESHOLD:
            statement_type = StatementType.UNKNOWN
            final_score = round(top_score, 3)
            evidence["classification_reason"] = f"Ambiguous: Margin between {top_st} ({top_score:.2f}) and {second_st} ({second_score:.2f}) < threshold ({self.SCORE_MARGIN_THRESHOLD})"
        else:
            statement_type = top_st
            evidence["classification_reason"] = f"Confident classification as {statement_type}"

        # Step 3: Extract Period Semantics
        period_type, fiscal_periods, period_context, has_yr, has_qtr, has_ttm = self._extract_period_semantics(table)

        # Step 4: Metric Label Normalization
        key_metrics = self._normalize_metrics(row_labels)

        return FinancialTableSemantics(
            statement_type=statement_type,
            confidence=final_score,
            period_type=period_type,
            fiscal_periods=fiscal_periods,
            period_context=period_context,
            currency=table.currency,
            units=table.units,
            has_year_columns=has_yr,
            has_quarter_columns=has_qtr,
            has_ttm_period=has_ttm,
            key_metrics=key_metrics,
            evidence=evidence,
        )

    def _extract_period_semantics(
        self, table: "ExtractedTable"
    ) -> tuple[str, list[str], str | None, bool, bool, bool]:
        """Extract fiscal periods, period types, and date context from headers and table title."""
        all_text = (table.title or "") + " " + " ".join(table.headers) + " " + " ".join([" ".join(r) for r in table.rows[:2]])
        
        # Years extraction (4-digit years between 2000 and 2035)
        years = re.findall(r"\b(20[0-3][0-9])\b", all_text)
        # Deduplicate preserving order
        fiscal_periods = list(dict.fromkeys(years))

        # Quarters extraction
        quarters = re.findall(r"\b(Q[1-4])\b", all_text, re.IGNORECASE)
        has_quarter_columns = len(quarters) > 0
        has_year_columns = len(fiscal_periods) > 0
        has_ttm_period = "ttm" in all_text.lower() or "trailing twelve months" in all_text.lower()

        # Period Context & Period Type detection
        period_context: str | None = None
        period_type = PeriodType.UNKNOWN

        # Search for explicit context phrases
        context_patterns = [
            (re.compile(r"Years?\s+Ended\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.ANNUAL),
            (re.compile(r"Three\s+Months?\s+Ended\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.QUARTERLY),
            (re.compile(r"Six\s+Months?\s+Ended\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.YEAR_TO_DATE),
            (re.compile(r"Nine\s+Months?\s+Ended\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.YEAR_TO_DATE),
            (re.compile(r"Month\s+Ended\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.MONTHLY),
            (re.compile(r"As\s+of\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.POINT_IN_TIME),
            (re.compile(r"At\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?", re.IGNORECASE), PeriodType.POINT_IN_TIME),
        ]

        for pattern, p_type in context_patterns:
            match = pattern.search(all_text)
            if match:
                period_context = match.group(0).strip()
                period_type = p_type
                break

        # Fallback period type heuristics if no explicit phrase match
        if period_type == PeriodType.UNKNOWN:
            if has_quarter_columns or "three months" in all_text.lower():
                period_type = PeriodType.QUARTERLY
            elif "year ended" in all_text.lower() or "years ended" in all_text.lower():
                period_type = PeriodType.ANNUAL
            elif "as of" in all_text.lower() or "balance sheet" in all_text.lower():
                period_type = PeriodType.POINT_IN_TIME
            elif has_year_columns and not has_quarter_columns:
                period_type = PeriodType.ANNUAL

        return period_type, fiscal_periods, period_context, has_year_columns, has_quarter_columns, has_ttm_period

    def _normalize_metrics(self, row_labels: list[str]) -> list[str]:
        """Normalize first-column row labels into standardized metric identifiers."""
        normalized_metrics = []
        for label in row_labels:
            clean_label = label.strip().lower()
            for raw_term, norm_metric in self.KNOWN_METRIC_MAP.items():
                if raw_term == clean_label or (len(raw_term) > 5 and raw_term in clean_label):
                    if norm_metric not in normalized_metrics:
                        normalized_metrics.append(norm_metric)
        return normalized_metrics
