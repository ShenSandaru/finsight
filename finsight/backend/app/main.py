import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestCorrelationMiddleware
from app.core.database import async_session
from app.core.rate_limit import get_redis_client, close_rate_limit_redis
from app.core.tasks import close_task_pool
from app.core.exceptions import (
    FinSightError,
    ValidationError,
    NotFoundError,
    ServiceError,
    ExternalServiceError,
    RateLimitExceeded,
)
from app.schemas.error import ErrorResponse, ErrorDetail
from app.api.routes import auth, documents, tasks, search, rag, conversations, reports
from sqlalchemy import text

settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = logging.getLogger("finsight.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info("Starting %s v%s [env_debug=%s, log_format=%s]", settings.APP_NAME, settings.APP_VERSION, settings.DEBUG, settings.LOG_FORMAT)
    logger.info("Ready to handle requests (schema managed via Alembic)")

    yield

    logger.info("Shutting down application resources...")
    await close_task_pool()
    await close_rate_limit_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered investment research copilot",
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(RequestCorrelationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# Standardized Exception Handlers
# ==========================================

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.message)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message=exc.message,
                details=exc.details,
            )
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("FastAPI request validation error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error=ErrorDetail(
                code="UNPROCESSABLE_ENTITY",
                message="Request validation failed",
                details=exc.errors(),
            )
        ).model_dump(),
    )


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    logger.info("Resource not found on %s %s: %s", request.method, request.url.path, exc.message)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(
            error=ErrorDetail(
                code="NOT_FOUND",
                message=exc.message,
                details=exc.details,
            )
        ).model_dump(),
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning("Rate limit exceeded on %s %s: %s", request.method, request.url.path, exc.message)
    headers = {
        "Retry-After": str(exc.retry_after),
        "X-RateLimit-Limit": str(exc.limit),
        "X-RateLimit-Remaining": "0",
    }
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers=headers,
        content=ErrorResponse(
            error=ErrorDetail(
                code="RATE_LIMIT_EXCEEDED",
                message=exc.message,
                details=exc.details,
            )
        ).model_dump(),
    )


@app.exception_handler(ExternalServiceError)
async def external_service_error_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
    logger.error("External service failure on %s %s: %s", request.method, request.url.path, exc.message, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(
            error=ErrorDetail(
                code="EXTERNAL_SERVICE_ERROR",
                message=exc.message,
                details=exc.details if settings.DEBUG else None,
            )
        ).model_dump(),
    )


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    logger.error("Internal service error on %s %s: %s", request.method, request.url.path, exc.message, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVICE_ERROR",
                message=exc.message,
                details=exc.details if settings.DEBUG else None,
            )
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal server error occurred",
                details={"error": str(exc)} if settings.DEBUG else None,
            )
        ).model_dump(),
    )


# Register routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Liveness check confirming the application process is running."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/ready")
async def readiness_check():
    """
    Readiness probe verifying critical infrastructure dependencies (PostgreSQL and Redis).
    Returns 200 if all critical dependencies are reachable, or 503 if any dependency is down.
    Never exposes internal connection strings or credentials.
    """
    checks = {
        "postgres": "unknown",
        "redis": "unknown",
    }
    all_healthy = True

    # 1. PostgreSQL Check: execute SELECT 1
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception as exc:
        logger.warning("Readiness probe: PostgreSQL check failed: %s", type(exc).__name__)
        checks["postgres"] = "unhealthy"
        all_healthy = False

    # 2. Redis Check: call ping()
    try:
        redis = get_redis_client()
        pong = await redis.ping()
        if pong:
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "unhealthy"
            all_healthy = False
    except Exception as exc:
        logger.warning("Readiness probe: Redis check failed: %s", type(exc).__name__)
        checks["redis"] = "unhealthy"
        all_healthy = False

    resp_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=resp_status,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
        },
    )