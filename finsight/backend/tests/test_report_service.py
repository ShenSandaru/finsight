"""Comprehensive unit and integration test suite for ReportService & API (Sprint 10.4)."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.core.exceptions import ValidationError, NotFoundError
from app.models.report import Report
from app.models.document import Document
from app.models.chunk import Chunk
from app.schemas.report import CreateReportRequest, ReportResponse, ReportListResponse
from app.services.report_service import ReportService
from app.agents.state import ResearchState, FinancialFinding
from app.services.rag_service import SourceCitation
from app.main import app

settings = get_settings()


class TestReportUnitAndMarkdownCompiler:

    def test_01_create_report_request_validation(self):
        # Valid request
        req = CreateReportRequest(query="What was Apple's 2025 revenue and gross margin?")
        assert req.query == "What was Apple's 2025 revenue and gross margin?"
        assert req.report_type == "financial_research"
        assert req.document_ids is None

    def test_02_create_report_request_bounds(self):
        with pytest.raises(Exception):
            CreateReportRequest(query="ab")  # min_length=3

        with pytest.raises(Exception):
            CreateReportRequest(query="a" * 1001)  # max_length=1000

    def test_03_markdown_report_compiler(self):
        doc_a_id = uuid.uuid4()
        doc_b_id = uuid.uuid4()
        chunk1_id = uuid.uuid4()
        chunk2_id = uuid.uuid4()

        findings = [
            FinancialFinding(
                metric="revenue",
                period="2025",
                value=1000.0,
                unit="$",
                document_id=doc_a_id,
                source_chunk_ids=[chunk1_id],
            ),
            FinancialFinding(
                metric="operating_margin",
                period="2025",
                value=28.5,
                unit="%",
                document_id=doc_a_id,
                source_chunk_ids=[chunk1_id],
                calculation="(operating_income / revenue) * 100",
            ),
            FinancialFinding(
                metric="revenue_cagr",
                period="2022_to_2025",
                value=14.47,
                unit="%",
                document_id=doc_a_id,
                source_chunk_ids=[chunk1_id],
                calculation="((150 / 100) ^ (1/3) - 1) * 100",
            ),
            FinancialFinding(
                metric="revenue_trend",
                period="2022_to_2025",
                value=1.0,
                unit="trend",
                document_id=doc_a_id,
                source_chunk_ids=[chunk1_id],
                calculation="Consistent Increase: [100 -> 115 -> 135 -> 150]",
            ),
            FinancialFinding(
                metric="revenue_comparison",
                period="2025_docB_vs_docA",
                value=50.0,
                unit="%",
                source_chunk_ids=[chunk1_id, chunk2_id],
                calculation="((150 - 100) / 100) * 100",
            ),
        ]

        citations = [
            SourceCitation(
                chunk_id=chunk1_id,
                document_id=doc_a_id,
                page_number=1,
                chunk_type="table",
                similarity=0.95,
                statement_type="income_statement",
                fiscal_periods=["2025", "2024"],
            ),
            SourceCitation(
                chunk_id=chunk2_id,
                document_id=doc_b_id,
                page_number=2,
                chunk_type="table",
                similarity=0.91,
                statement_type="income_statement",
                fiscal_periods=["2025"],
            ),
        ]

        state: ResearchState = {
            "original_query": "Compare revenue and margins",
            "standalone_query": "Compare revenue and margins",
            "sub_queries": [],
            "retrieved_chunks": [],
            "findings": findings,
            "citations": citations,
            "final_answer": "Company A achieved $1,000M revenue with a 28.5% operating margin [SOURCE 1].",
            "session_id": None,
            "document_id": None,
            "document_ids": [doc_a_id, doc_b_id],
            "top_k": 5,
            "min_similarity": 0.0,
            "citation_audit": None,
            "guardrails_validation": None,
            "grounded": True,
            "step_count": 5,
            "status": "completed",
            "error": None,
        }

        md = ReportService.compile_markdown_report(
            title="Comparative Revenue Analysis",
            query="Compare revenue and margins",
            state=state,
        )

        assert "# Financial Research Report: Comparative Revenue Analysis" in md
        assert "## 1. Executive Summary" in md
        assert "Company A achieved $1,000M revenue" in md
        assert "## 2. Key Financial Metrics & Calculated Ratios" in md
        assert "operating_margin" in md
        assert "## 3. Historical Trends & CAGR Analysis" in md
        assert "revenue_cagr" in md
        assert "Consistent Increase" in md
        assert "## 4. Cross-Document & Peer Comparison" in md
        assert "revenue_comparison" in md
        assert "## 5. Source Evidence & Citations" in md
        assert "[SOURCE 1]" in md
        assert "[SOURCE 2]" in md


@pytest.mark.asyncio
class TestReportDatabaseAndAPIOperations:

    async def test_04_create_and_get_report_crud(self, db_session_factory):
        async with db_session_factory() as session:
            service = ReportService()
            req = CreateReportRequest(query="Analyze FCF for 2025", title="FCF Report")
            report = await service.create_report_record(request=req, db=session)

            assert report.id is not None
            assert report.title == "FCF Report"
            assert report.query == "Analyze FCF for 2025"
            assert report.status == "pending"

            retrieved = await service.get_report(report_id=report.id, db=session)
            assert retrieved.id == report.id
            assert retrieved.title == "FCF Report"

            # Cleanup
            await service.delete_report(report_id=report.id, db=session)

            with pytest.raises(NotFoundError):
                await service.get_report(report_id=report.id, db=session)

    async def test_05_list_reports_with_filter(self, db_session_factory):
        async with db_session_factory() as session:
            service = ReportService()
            r1 = await service.create_report_record(request=CreateReportRequest(query="Query 1", title="Report 1"), db=session)
            r2 = await service.create_report_record(request=CreateReportRequest(query="Query 2", title="Report 2"), db=session)

            # Update r2 to completed
            r2.status = "completed"
            await session.commit()

            # List all
            res_all = await service.list_reports(limit=10, db=session)
            assert res_all.total >= 2

            # Filter by status
            res_completed = await service.list_reports(status="completed", limit=10, db=session)
            assert any(r.id == r2.id for r in res_completed.reports)
            assert not any(r.id == r1.id for r in res_completed.reports)

            # Cleanup
            await service.delete_report(r1.id, db=session)
            await service.delete_report(r2.id, db=session)

    async def test_06_report_endpoints_http(self, db_session_factory, monkeypatch):
        from app.core.database import get_db

        async def override_get_db():
            async with db_session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        # Mock enqueue_task so test doesn't require live Redis connection
        async def mock_enqueue(task_name: str, *args, **kwargs):
            return "mock-job-id"

        monkeypatch.setattr("app.api.routes.reports.enqueue_task", mock_enqueue)

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # 1. Create Report via POST
                create_payload = {
                    "query": "What was Apple's gross margin in 2025?",
                    "title": "Apple Margin 2025",
                }
                resp = await client.post("/api/v1/reports", json=create_payload)
                assert resp.status_code == 202
                data = resp.json()
                assert data["status"] == "pending"
                assert data["title"] == "Apple Margin 2025"
                rep_id = data["id"]

                # 2. Get Report via GET
                get_resp = await client.get(f"/api/v1/reports/{rep_id}")
                assert get_resp.status_code == 200
                assert get_resp.json()["id"] == rep_id

                # 3. List Reports
                list_resp = await client.get("/api/v1/reports")
                assert list_resp.status_code == 200
                assert list_resp.json()["total"] >= 1

                # 4. Delete Report
                del_resp = await client.delete(f"/api/v1/reports/{rep_id}")
                assert del_resp.status_code == 204

                # 5. Verify 404 after deletion
                get_after_del = await client.get(f"/api/v1/reports/{rep_id}")
                assert get_after_del.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)
