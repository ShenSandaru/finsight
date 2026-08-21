import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.tasks import close_task_pool
from app.core.exceptions import (
    FinSightError,
    ValidationError,
    NotFoundError,
    ServiceError,
    ExternalServiceError,
)
from app.schemas.error import ErrorResponse, ErrorDetail
from app.api.routes import documents, tasks

logger = logging.getLogger("finsight.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print("✅ Ready to handle requests (schema managed via Alembic)")

    yield

    print("👋 Shutting down...")
    await close_task_pool()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered investment research copilot",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
app.include_router(documents.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }