"""Redis and ARQ task queue client management."""

import logging
from typing import Any
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger("finsight.tasks")
settings = get_settings()

_redis_pool: ArqRedis | None = None


def get_redis_settings() -> RedisSettings:
    """Return ARQ RedisSettings based on application configuration."""
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
    )


async def get_task_pool() -> ArqRedis:
    """
    Get or initialize the singleton ArqRedis connection pool.
    Raises ExternalServiceError if unable to connect to Redis.
    """
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = await create_pool(
                get_redis_settings(),
                default_queue_name=settings.ARQ_QUEUE_NAME,
            )
            logger.info("Connected to Redis task queue (%s:%s)", settings.REDIS_HOST, settings.REDIS_PORT)
        except Exception as exc:
            logger.error("Failed to connect to Redis task queue: %s", exc)
            raise ExternalServiceError("Could not connect to Redis task queue", details={"error": str(exc)}) from exc
    return _redis_pool


async def close_task_pool() -> None:
    """Close the ArqRedis connection pool on application shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Closed Redis task queue connection pool")


async def enqueue_task(task_name: str, *args: Any, **kwargs: Any) -> str | None:
    """
    Enqueue a background job by function name.
    Returns the job ID if queued successfully.
    """
    pool = await get_task_pool()
    try:
        job = await pool.enqueue_job(task_name, *args, **kwargs)
        if job:
            logger.info("Enqueued task '%s' [job_id=%s]", task_name, job.job_id)
            return job.job_id
        return None
    except Exception as exc:
        logger.error("Failed to enqueue task '%s': %s", task_name, exc)
        raise ExternalServiceError(f"Failed to enqueue task: {task_name}", details={"error": str(exc)}) from exc
