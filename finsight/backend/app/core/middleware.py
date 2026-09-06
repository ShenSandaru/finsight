"""Request correlation ID and lifecycle logging middleware for FinSight (Phase 12.5).

Intercepts incoming requests, validates/generates X-Request-ID, binds it to ContextVar,
records request duration, emits canonical structured access logs, and attaches X-Request-ID
to the outgoing response. Never logs request bodies, authorization headers, cookies,
or query strings.
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import (
    correlation_id_ctx,
    sanitize_request_id,
)

logger = logging.getLogger("finsight.access")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware managing request correlation ID lifecycle and safe request logging.

    1. Extracts X-Request-ID header, validates against safe regex (max 64 chars, no control chars).
    2. Generates a fresh UUID4 if absent, invalid, or oversized.
    3. Binds request_id to contextvars.ContextVar for request scope and resets it in finally block.
    4. Records execution duration and logs method, path (without query string), status code, and duration.
    5. Injects X-Request-ID header into the response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming_header = request.headers.get("X-Request-ID")
        request_id = sanitize_request_id(incoming_header)

        # Establish request-scoped ContextVar
        token = correlation_id_ctx.set(request_id)
        start_time = time.perf_counter()

        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            status_code = response.status_code

            # Attach X-Request-ID and standard security headers to outgoing response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Safe structured logging: only method, path, status, and duration
            extra_data = {
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }

            # Optional user ID if naturally attached to request.state by dependency
            user = getattr(request.state, "current_user", None)
            if user and hasattr(user, "id"):
                extra_data["user_id"] = str(user.id)

            if status_code >= 500:
                logger.error(
                    "Request completed with server error: %s %s -> %d (%.2fms)",
                    method, path, status_code, duration_ms,
                    extra=extra_data,
                )
            elif status_code >= 400:
                logger.warning(
                    "Request completed with client error: %s %s -> %d (%.2fms)",
                    method, path, status_code, duration_ms,
                    extra=extra_data,
                )
            else:
                logger.info(
                    "Request completed: %s %s -> %d (%.2fms)",
                    method, path, status_code, duration_ms,
                    extra=extra_data,
                )

            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            extra_data = {
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": 500,
                "duration_ms": duration_ms,
                "exception_type": type(exc).__name__,
            }
            logger.error(
                "Request failed with unhandled exception: %s %s (%.2fms)",
                method, path, duration_ms,
                extra=extra_data,
                exc_info=True,
            )
            raise exc

        finally:
            # Cleanly reset ContextVar to prevent correlation ID leakage across tasks
            correlation_id_ctx.reset(token)
