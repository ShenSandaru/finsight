"""Financial Research Report API endpoints (Sprint 10.4)."""

import logging
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.user import User
from app.core.database import get_db
from app.core.tasks import enqueue_task
from app.schemas.report import CreateReportRequest, ReportResponse, ReportListResponse
from app.services.report_service import ReportService

from app.core.rate_limit import rate_limit

logger = logging.getLogger("finsight.api.routes.reports")
router = APIRouter(prefix="/reports", tags=["Financial Research Reports"])


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("reports", fail_closed=True))],
    summary="Create and enqueue an asynchronous financial research report",
    description="Submits a structured financial research report request to the background ARQ worker queue. Returns HTTP 202 with initial 'pending' status.",
)
async def create_report(
    request: CreateReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """
    Create a new report record and enqueue report generation job (scoped to user).
    """
    report_service = ReportService()
    report = await report_service.create_report_record(request=request, user_id=current_user.id, db=db)

    try:
        job_id = await enqueue_task("generate_financial_report", str(report.id))
        logger.info("Enqueued report generation task for report %s [job_id=%s]", report.id, job_id)
    except Exception as exc:
        logger.error("Failed to enqueue report generation task for report %s: %s", report.id, exc)
        # Mark as failed if we cannot queue to Redis
        report.status = "failed"
        report.error_message = "Failed to enqueue report job to worker queue"
        await db.commit()
        await db.refresh(report)

    return ReportService._format_report_response(report)


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get financial research report status, content, and citations",
)
async def get_report_by_id(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """
    Retrieve report details, progress status, full Markdown content, and citations (scoped to user).
    """
    report_service = ReportService()
    report = await report_service.get_report(report_id=report_id, user_id=current_user.id, db=db)
    return ReportService._format_report_response(report)


@router.get(
    "",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List financial research reports",
)
async def list_reports(
    status_filter: str | None = Query(None, alias="status", description="Filter reports by status: pending, processing, completed, failed"),
    limit: int = Query(50, ge=1, le=100, description="Max number of reports to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportListResponse:
    """
    List reports sorted by creation date descending with optional status filtering (scoped to user).
    """
    report_service = ReportService()
    return await report_service.list_reports(user_id=current_user.id, status=status_filter, limit=limit, offset=offset, db=db)


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a financial research report",
)
async def delete_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a report record. Does not affect source documents, chunks, or conversation sessions (scoped to user).
    """
    report_service = ReportService()
    await report_service.delete_report(report_id=report_id, user_id=current_user.id, db=db)
