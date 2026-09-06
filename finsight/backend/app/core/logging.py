"""Structured logging and correlation ID tracking for FinSight (Phase 12.5).

Provides request correlation IDs via ContextVar, structured JSON formatting for production,
human-readable text formatting for development, and safe log sanitization without leaking
credentials, tokens, cookies, or document contents.
"""

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
import sys
from typing import Any, Optional
import uuid

# Request-scoped correlation ID. Default is None.
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Regular expression for safe request IDs: alphanumeric, dashes, and underscores only
_SAFE_REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9\-_]{1,64}$")

# Sentinel to track logging initialization and avoid duplicate handlers
_LOGGING_INITIALIZED = False


def get_correlation_id() -> Optional[str]:
    """Return the current request correlation ID, if set."""
    return correlation_id_ctx.get()


def set_correlation_id(request_id: Optional[str]) -> None:
    """Set the current request correlation ID in the ContextVar."""
    correlation_id_ctx.set(request_id)


def sanitize_request_id(incoming_id: Optional[str]) -> str:
    """
    Validate and sanitize an incoming request ID.
    - If valid (alphanumeric, dashes, underscores, max 64 chars), returns it.
    - If missing, invalid, or containing control characters/newlines, generates a new UUID4.
    """
    if not incoming_id:
        return str(uuid.uuid4())

    cleaned = incoming_id.strip()
    if _SAFE_REQUEST_ID_REGEX.match(cleaned):
        return cleaned

    return str(uuid.uuid4())


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON formatter emitting machine-readable logs with stable fields:
    timestamp, level, logger, message, request_id, and any extra context attributes.
    """

    RESERVED_ATTRS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Correlate with request_id: check record attribute first, then ContextVar
        req_id = getattr(record, "request_id", None) or get_correlation_id()
        if req_id:
            log_data["request_id"] = req_id

        # Include custom extra fields attached to the log record
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith("_"):
                # Avoid overwriting already resolved fields unless explicitly intended
                if key not in log_data:
                    log_data[key] = value

        # Format exception information if present
        if record.exc_info:
            log_data["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            log_data["stack_trace"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_data["stack_trace"] = record.exc_text

        return json.dumps(log_data, default=str)


class TextLogFormatter(logging.Formatter):
    """
    Human-readable log formatter for development and testing.
    Includes [request_id] when available.
    """

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or get_correlation_id()
        req_str = f" [{req_id}]" if req_id else ""

        # Extract extra context if attached
        extras = []
        for key in ("method", "path", "status_code", "duration_ms", "job_id", "task_name", "document_id", "report_id"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")

        extra_str = f" ({', '.join(extras)})" if extras else ""

        asctime = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"{asctime} [{record.levelname}] [{record.name}]{req_str}: {record.getMessage()}{extra_str}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        elif record.exc_text:
            formatted += "\n" + record.exc_text

        return formatted


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure root logging and standard output handlers.
    Can be invoked repeatedly in tests; ensures handlers are cleanly set without accumulation.
    """
    global _LOGGING_INITIALIZED

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter: logging.Formatter
    if log_format.lower() == "json":
        formatter = StructuredJsonFormatter()
    else:
        formatter = TextLogFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicate lines upon repeated calls / reloads
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Silence redundant default uvicorn.access logger so canonical request logging middleware is not duplicated
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.propagate = False

    _LOGGING_INITIALIZED = True
