"""Unit test suite for FinancialTableSemanticService (Sprint 4.2)."""

import pytest
from app.services.table_extractor import ExtractedTable
from app.services.table_semantics import (
    FinancialTableSemanticService,
    StatementType,
    PeriodType,
    FinancialTableSemantics,
)


@pytest.fixture
def service():
    return FinancialTableSemanticService()


def create_mock_table(
    table_id: str = "tbl_1_1",
    title: str | None = None,
    headers: list[str] | None = None,
    rows: list[list[str]] | None = None,
    currency: str | None = "$",
    units: str | None = "millions",
) -> ExtractedTable:
    headers = headers or ["Col 1", "2025", "2024"]
    rows = rows or [["Sample Line", "100", "90"]]
    return ExtractedTable(
        table_id=table_id,
        document_id="doc_test_123",
        page_number=1,
        headers=headers,
        rows=rows,
        column_count=len(headers),
        row_count=len(rows),
        title=title,
        currency=currency,
        units=units,
        markdown="",
    )


class TestTableSemanticsClassification:

    def test_01_income_statement_classification(self, service):
        tbl = create_mock_table(
            title="Consolidated Statements of Operations",
            headers=["(in millions)", "Years Ended Dec 31, 2025", "2024"],
            rows=[
                ["Total Revenue", "$1,000", "$900"],
                ["Cost of Sales", "$600", "$550"],
                ["Gross Profit", "$400", "$350"],
                ["Operating Expenses", "$200", "$180"],
                ["Operating Income", "$200", "$170"],
                ["Net Income", "$150", "$130"],
                ["Earnings Per Share", "$1.50", "$1.30"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.INCOME_STATEMENT
        assert sem.confidence >= 0.60
        assert sem.period_type == PeriodType.ANNUAL
        assert "2025" in sem.fiscal_periods
        assert "2024" in sem.fiscal_periods
        assert "net_income" in sem.key_metrics
        assert "revenue" in sem.key_metrics
        assert sem.currency == "$"
        assert sem.units == "millions"

    def test_02_balance_sheet_classification(self, service):
        tbl = create_mock_table(
            title="Consolidated Balance Sheets",
            headers=["(in thousands)", "As of Dec 31, 2025", "Dec 31, 2024"],
            rows=[
                ["Cash and cash equivalents", "$500", "$450"],
                ["Accounts receivable", "$300", "$280"],
                ["Total Current Assets", "$800", "$730"],
                ["Total Assets", "$1,500", "$1,400"],
                ["Accounts payable", "$200", "$190"],
                ["Total Liabilities", "$600", "$550"],
                ["Retained earnings", "$900", "$850"],
                ["Total Stockholders' Equity", "$900", "$850"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.BALANCE_SHEET
        assert sem.confidence >= 0.60
        assert sem.period_type == PeriodType.POINT_IN_TIME
        assert "total_assets" in sem.key_metrics
        assert "total_liabilities" in sem.key_metrics
        assert "cash_and_cash_equivalents" in sem.key_metrics

    def test_03_cash_flow_classification(self, service):
        tbl = create_mock_table(
            title="Consolidated Statements of Cash Flows",
            headers=["Years Ended Dec 31,", "2025", "2024"],
            rows=[
                ["Operating activities", "", ""],
                ["Net Cash Provided by Operating Activities", "$300", "$280"],
                ["Investing activities", "", ""],
                ["Capital expenditures", "($100)", "($90)"],
                ["Financing activities", "", ""],
                ["Net Cash Provided by Financing Activities", "($50)", "($40)"],
                ["Cash and Cash Equivalents at End of Period", "$500", "$350"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.CASH_FLOW
        assert sem.confidence >= 0.60
        assert sem.period_type == PeriodType.ANNUAL
        assert "operating_cash_flow" in sem.key_metrics
        assert "capital_expenditures" in sem.key_metrics

    def test_04_stockholders_equity_classification(self, service):
        tbl = create_mock_table(
            title="Statements of Stockholders' Equity",
            headers=["Common Stock", "Retained Earnings", "Total Equity"],
            rows=[
                ["Balance at Beginning of Period", "$100", "$400", "$500"],
                ["Additional Paid-in Capital", "$50", "$0", "$50"],
                ["Dividends Declared", "$0", "($20)", "($20)"],
                ["Treasury Stock", "($10)", "$0", "($10)"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.STOCKHOLDERS_EQUITY
        assert sem.confidence >= 0.50

    def test_05_comprehensive_income_classification(self, service):
        tbl = create_mock_table(
            title="Statements of Comprehensive Income",
            headers=["Years Ended Dec 31,", "2025", "2024"],
            rows=[
                ["Net income", "$100", "$90"],
                ["Other Comprehensive Income", "", ""],
                ["Foreign currency translation", "$10", "($5)"],
                ["Unrealized gains on securities", "$5", "$2"],
                ["Total Comprehensive Income", "$115", "$87"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.COMPREHENSIVE_INCOME
        assert sem.confidence >= 0.50

    def test_06_debt_classification(self, service):
        tbl = create_mock_table(
            title="Note 7: Long-Term Debt and Borrowings",
            headers=["Description", "Effective Interest Rate", "Principal Amount"],
            rows=[
                ["Senior Notes due 2028", "4.5%", "$500"],
                ["Term Loans", "5.2%", "$300"],
                ["Revolving Credit Facility", "3.8%", "$100"],
                ["Maturities of Debt", "", "$900"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.DEBT
        assert sem.confidence >= 0.40

    def test_07_revenue_breakdown_classification(self, service):
        tbl = create_mock_table(
            title="Disaggregated Revenue by Product Line",
            headers=["Product Line", "2025", "2024"],
            rows=[
                ["Product Revenue", "$600", "$500"],
                ["Service Revenue", "$300", "$250"],
                ["Subscription Revenue", "$100", "$80"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.REVENUE_BREAKDOWN
        assert sem.confidence >= 0.40

    def test_08_unknown_classification(self, service):
        tbl = create_mock_table(
            title=None,
            headers=["Name", "Age", "Department"],
            rows=[
                ["John Doe", "34", "Engineering"],
                ["Jane Smith", "28", "Marketing"],
            ],
            currency=None,
            units=None,
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.UNKNOWN
        assert sem.confidence == 0.0

    def test_09_ambiguous_classification_conservative(self, service):
        # Table with mixed terms giving close scores
        tbl = create_mock_table(
            title=None,
            headers=["Metric", "2025"],
            rows=[
                ["Revenue", "$100"],
                ["Total Assets", "$100"],
            ],
        )
        sem = service.analyze_table(tbl)
        # Should default to unknown due to ambiguity margin or low score
        assert sem.statement_type == StatementType.UNKNOWN or sem.confidence < 0.40

    def test_10_title_based_weighting(self, service):
        tbl = create_mock_table(
            title="Consolidated Statements of Operations",
            headers=["Col A", "Col B"],
            rows=[["Line 1", "100"]],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.INCOME_STATEMENT
        assert sem.confidence >= 0.60
        assert len(sem.evidence["title_matches"]) == 1

    def test_11_row_label_weighting(self, service):
        tbl = create_mock_table(
            title=None,
            headers=["Col 1", "Col 2"],
            rows=[
                ["Total Revenue", "$100"],
                ["Cost of Sales", "$60"],
                ["Gross Profit", "$40"],
                ["Net Income", "$20"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert sem.statement_type == StatementType.INCOME_STATEMENT
        assert sem.confidence >= 0.50

    def test_12_fiscal_period_extraction(self, service):
        tbl = create_mock_table(
            title="Revenue Comparison",
            headers=["Segment", "2025", "2024", "2023"],
            rows=[["Software", "100", "90", "80"]],
        )
        sem = service.analyze_table(tbl)
        assert sem.fiscal_periods == ["2025", "2024", "2023"]
        assert sem.has_year_columns is True
        assert sem.has_quarter_columns is False

    def test_13_annual_period_type(self, service):
        tbl = create_mock_table(
            title="Years Ended December 31, 2025 and 2024",
            headers=["Item", "2025", "2024"],
            rows=[["Revenue", "100", "90"]],
        )
        sem = service.analyze_table(tbl)
        assert sem.period_type == PeriodType.ANNUAL
        assert sem.period_context == "Years Ended December 31, 2025"

    def test_14_quarterly_period_type(self, service):
        tbl = create_mock_table(
            title="Three Months Ended March 31, 2025",
            headers=["Metric", "Q1 2025", "Q1 2024"],
            rows=[["Revenue", "100", "90"]],
        )
        sem = service.analyze_table(tbl)
        assert sem.period_type == PeriodType.QUARTERLY
        assert sem.has_quarter_columns is True
        assert sem.period_context == "Three Months Ended March 31, 2025"

    def test_15_year_to_date_period_type(self, service):
        tbl = create_mock_table(
            title="Six Months Ended June 30, 2025",
            headers=["Metric", "2025", "2024"],
            rows=[["Revenue", "100", "90"]],
        )
        sem = service.analyze_table(tbl)
        assert sem.period_type == PeriodType.YEAR_TO_DATE
        assert sem.period_context == "Six Months Ended June 30, 2025"

    def test_16_point_in_time_period_type(self, service):
        tbl = create_mock_table(
            title="As of December 31, 2025",
            headers=["Asset Class", "2025"],
            rows=[["Cash", "100"]],
        )
        sem = service.analyze_table(tbl)
        assert sem.period_type == PeriodType.POINT_IN_TIME
        assert sem.period_context == "As of December 31, 2025"

    def test_17_metric_normalization(self, service):
        tbl = create_mock_table(
            title="Financial Overview",
            headers=["Item", "2025"],
            rows=[
                ["Total Revenue", "100"],
                ["Gross Profit", "40"],
                ["Operating Income", "25"],
                ["Net Income", "20"],
            ],
        )
        sem = service.analyze_table(tbl)
        assert "revenue" in sem.key_metrics
        assert "gross_profit" in sem.key_metrics
        assert "operating_income" in sem.key_metrics
        assert "net_income" in sem.key_metrics

    def test_18_currency_and_units_propagation(self, service):
        tbl = create_mock_table(
            title="Balance Sheet",
            currency="EUR",
            units="thousands",
        )
        sem = service.analyze_table(tbl)
        assert sem.currency == "EUR"
        assert sem.units == "thousands"

    def test_19_confidence_score_determinism(self, service):
        tbl = create_mock_table(
            title="Consolidated Statements of Operations",
            headers=["Item", "2025"],
            rows=[["Net Income", "100"]],
        )
        sem1 = service.analyze_table(tbl)
        sem2 = service.analyze_table(tbl)
        assert sem1.confidence == sem2.confidence
        assert sem1.statement_type == sem2.statement_type
        assert sem1.evidence == sem2.evidence

    def test_20_evidence_structure(self, service):
        tbl = create_mock_table(
            title="Consolidated Statements of Cash Flows",
            rows=[["Net cash provided by operating activities", "100"]],
        )
        sem = service.analyze_table(tbl)
        assert "title_matches" in sem.evidence
        assert "row_matches" in sem.evidence
        assert "score_components" in sem.evidence
        assert "top_score" in sem.evidence
        assert "second_score" in sem.evidence
        assert "classification_reason" in sem.evidence
