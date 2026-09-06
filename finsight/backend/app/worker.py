"""ARQ Worker process entry point for FinSight."""

import logging
from typing import Any
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.tasks.definitions import health_check_task, failing_test_task, process_document, generate_financial_report

settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = logging.getLogger("finsight.worker")


async def startup(ctx: dict[str, Any]) -> None:
    """Invoked when the background worker boots."""
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info("FinSight ARQ Worker starting up...")
    logger.info("Connected to queue '%s' on Redis (%s:%s)", settings.ARQ_QUEUE_NAME, settings.REDIS_HOST, settings.REDIS_PORT)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Invoked when the background worker is gracefully stopped."""
    logger.info("👋 FinSight ARQ Worker shutting down...")


class WorkerSettings:
    """ARQ Worker configuration class."""

    functions = [
        health_check_task,
        failing_test_task,
        process_document,
        generate_financial_report,
    ]
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
    )
    queue_name = settings.ARQ_QUEUE_NAME
    max_tries = settings.TASK_MAX_TRIES
    job_timeout = settings.TASK_TIMEOUT_SECONDS
    on_startup = startup
    on_shutdown = shutdown
