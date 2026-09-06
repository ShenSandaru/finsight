"""Unit and integration tests for FinSight Phase 12.5 Production Observability & Structured Logging.

Covers:
1. Correlation ID generation, validation, sanitization, and propagation.
2. ContextVar request isolation across concurrent executions.
3. StructuredJsonFormatter format, fields, and exception serialization.
4. Request correlation middleware lifecycle logging (method, path, status, duration).
5. Strict exclusion of sensitive data (cookies, auth headers, query parameters, document contents).
6. /health liveness probe independence.
7. /ready readiness probe dependency verification (PostgreSQL and Redis checks).
8. Worker task structured logging and context isolation.
"""

import asyncio
from contextvars import copy_context
import json
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.core.logging import (
    correlation_id_ctx,
    get_correlation_id,
    set_correlation_id,
    sanitize_request_id,
    StructuredJsonFormatter,
    TextLogFormatter,
    setup_logging,
)
from app.main import app

settings = get_settings()


class TestRequestCorrelationID:
    """Tests correlation ID validation, generation, and sanitization."""

    def test_sanitize_request_id_valid(self):
        valid_id = "req-12345_ABC-xyz"
        assert sanitize_request_id(valid_id) == valid_id

    def test_sanitize_request_id_missing_generates_uuid(self):
        new_id = sanitize_request_id(None)
        assert uuid.UUID(new_id)  # Should parse as valid UUID

        empty_id = sanitize_request_id("")
        assert uuid.UUID(empty_id)

    def test_sanitize_request_id_oversized_replaced(self):
        oversized = "a" * 65
        sanitized = sanitize_request_id(oversized)
        assert sanitized != oversized
        assert uuid.UUID(sanitized)

    def test_sanitize_request_id_injection_control_chars(self):
        injection = "req-1\n[ERROR] Fake Log Line\r\n"
        sanitized = sanitize_request_id(injection)
        assert "\n" not in sanitized
        assert "\r" not in sanitized
        assert uuid.UUID(sanitized)

    def test_contextvar_isolation_concurrent(self):
        """Verify concurrent async contexts do not leak correlation IDs."""
        async def task_worker(assigned_id: str):
            set_correlation_id(assigned_id)
            await asyncio.sleep(0.01)
            assert get_correlation_id() == assigned_id

        async def run_concurrent():
            ids = [f"req-thread-{i}" for i in range(10)]
            await asyncio.gather(*(task_worker(i) for i in ids))

        asyncio.run(run_concurrent())


class TestStructuredJsonFormatter:
    """Tests JSON formatter output fields and structure."""

    def test_json_formatter_fields(self):
        formatter = StructuredJsonFormatter()
        logger = logging.getLogger("test.logger")
        record = logger.makeRecord(
            name="test.logger",
            level=logging.INFO,
            fn="test.py",
            lno=10,
            msg="User action performed",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-req-id-123"
        record.method = "GET"
        record.path = "/api/v1/documents"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "User action performed"
        assert data["request_id"] == "test-req-id-123"
        assert data["method"] == "GET"
        assert data["path"] == "/api/v1/documents"
        assert "timestamp" in data

    def test_json_formatter_exception_serialization(self):
        formatter = StructuredJsonFormatter()
        logger = logging.getLogger("test.error")

        try:
            raise ValueError("Invalid financial calculation input")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logger.makeRecord(
            name="test.error",
            level=logging.ERROR,
            fn="test.py",
            lno=20,
            msg="Calculation failed",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert data["exception_type"] == "ValueError"
        assert "Invalid financial calculation input" in data["stack_trace"]


@pytest.mark.asyncio
class TestObservabilityMiddlewareIntegration:
    """Tests HTTP request correlation ID lifecycle and safe request logging."""

    async def test_request_id_in_response_header_generated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/health")
            assert resp.status_code == 200
            assert "X-Request-ID" in resp.headers
            assert uuid.UUID(resp.headers["X-Request-ID"])

    async def test_request_id_in_response_header_propagated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            custom_id = "client-trace-id-998877"
            resp = await ac.get("/health", headers={"X-Request-ID": custom_id})
            assert resp.status_code == 200
            assert resp.headers["X-Request-ID"] == custom_id

    async def test_sensitive_data_not_logged_query_string_stripped(self, caplog):
        """Verify sensitive query parameters (OAuth callback code/state) are not logged by finsight."""
        transport = ASGITransport(app=app)
        caplog.set_level(logging.INFO)

        secret_code = "SECRET_OAUTH_CODE_XYZ"
        secret_state = "SECRET_OAUTH_STATE_123"

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Hit callback with secrets in query string
            await ac.get(f"/api/v1/auth/google/callback?code={secret_code}&state={secret_state}")

        finsight_logs = [r.getMessage() for r in caplog.records if r.name.startswith("finsight")]
        finsight_text = " ".join(finsight_logs)
        assert secret_code not in finsight_text
        assert secret_state not in finsight_text
        assert "/api/v1/auth/google/callback" in finsight_text

    async def test_sensitive_headers_and_cookies_not_in_logs(self, caplog):
        """Verify authorization headers and session cookies never enter logs."""
        transport = ASGITransport(app=app)
        caplog.set_level(logging.INFO)

        secret_cookie = "SUPER_SECRET_SESSION_TOKEN_ABC"
        secret_auth = "Bearer SECRET_BEARER_TOKEN"

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.get(
                "/health",
                headers={"Authorization": secret_auth},
                cookies={"finsight_session": secret_cookie},
            )

        captured_text = caplog.text
        assert secret_cookie not in captured_text
        assert secret_auth not in captured_text


@pytest.mark.asyncio
class TestHealthAndReadinessEndpoints:
    """Tests /health (liveness) and /ready (readiness) endpoints."""

    async def test_liveness_endpoint_independent_of_dependencies(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["app"] == settings.APP_NAME

    async def test_readiness_both_healthy(self):
        transport = ASGITransport(app=app)

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("app.main.async_session", return_value=mock_session_cm):
            with patch("app.main.get_redis_client", return_value=mock_redis):
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    resp = await ac.get("/ready")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "ready"
                    assert data["checks"]["postgres"] == "healthy"
                    assert data["checks"]["redis"] == "healthy"

    async def test_readiness_postgres_unhealthy(self):
        transport = ASGITransport(app=app)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.side_effect = ConnectionRefusedError("PostgreSQL connection refused")

        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        with patch("app.main.async_session", return_value=mock_session_cm):
            with patch("app.main.get_redis_client", return_value=mock_redis):
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    resp = await ac.get("/ready")
                    assert resp.status_code == 503
                    data = resp.json()
                    assert data["status"] == "not_ready"
                    assert data["checks"]["postgres"] == "unhealthy"
                    assert data["checks"]["redis"] == "healthy"
                    # Confirm no internal connection strings leaked
                    assert "password" not in json.dumps(data)
                    assert "postgresql" not in json.dumps(data)

    async def test_readiness_redis_unhealthy(self):
        transport = ASGITransport(app=app)

        mock_session = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = ConnectionError("Redis down")

        with patch("app.main.async_session", return_value=mock_session_cm):
            with patch("app.main.get_redis_client", return_value=mock_redis):
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    resp = await ac.get("/ready")
                    assert resp.status_code == 503
                    data = resp.json()
                    assert data["status"] == "not_ready"
                    assert data["checks"]["postgres"] == "healthy"
                    assert data["checks"]["redis"] == "unhealthy"


class TestWorkerLoggingObservability:
    """Tests worker structured task logging."""

    @pytest.mark.asyncio
    async def test_worker_health_check_task_logs(self, caplog):
        from app.tasks.definitions import health_check_task
        caplog.set_level(logging.INFO)

        ctx = {"job_id": "test-job-uuid-1122"}
        result = await health_check_task(ctx, message="Ping worker")

        assert result["status"] == "success"
        assert result["job_id"] == "test-job-uuid-1122"
        assert "Completed health_check_task [job_id=test-job-uuid-1122]" in caplog.text
