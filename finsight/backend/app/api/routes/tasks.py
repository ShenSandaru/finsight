"""Routes for testing and monitoring asynchronous tasks."""

import uuid
from typing import Any
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.tasks import enqueue_task

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TestTaskRequest(BaseModel):
    message: str = Field(default="Hello from FinSight test task", description="Message payload to send to task worker")


class FailingTaskRequest(BaseModel):
    error_reason: str = Field(default="Test worker exception resilience", description="Simulated failure reason")


class TaskEnqueueResponse(BaseModel):
    status: str
    task_name: str
    job_id: str | None
    message: str


@router.post(
    "/test-health",
    response_model=TaskEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_health_task(payload: TestTaskRequest):
    """
    Enqueue a health check task to Redis for execution by the background worker.
    """
    job_id = await enqueue_task("health_check_task", payload.message)
    return TaskEnqueueResponse(
        status="enqueued",
        task_name="health_check_task",
        job_id=job_id,
        message="Health check task enqueued successfully to Redis worker",
    )


@router.post(
    "/test-failure",
    response_model=TaskEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_failing_task(payload: FailingTaskRequest):
    """
    Enqueue a deliberately failing task to verify worker resilience and exception handling.
    """
    job_id = await enqueue_task("failing_test_task", payload.error_reason)
    return TaskEnqueueResponse(
        status="enqueued",
        task_name="failing_test_task",
        job_id=job_id,
        message="Failing test task enqueued successfully",
    )
