"""ARQ Worker process entry point for FinSight."""

import logging
from typing import Any
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.tasks.definitions import health_check_task, failing_test_task, process_document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("finsight.worker")
settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    """Invoked when the background worker boots."""
    logger.info("🚀 FinSight ARQ Worker starting up...")
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
