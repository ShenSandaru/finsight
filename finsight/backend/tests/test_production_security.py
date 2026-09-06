"""Unit and integration security regression tests for FinSight Phase 12.6.

Covers:
1. Standard security response headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy).
2. Host-header protection via TrustedHostMiddleware (allowed vs untrusted hosts).
3. CORS configuration validation (credentialed safety, wildcard rejection).
4. Secure cookie configuration rules (production vs development).
5. Production debug safeguards (ENVIRONMENT=production with DEBUG=True rejected).
6. Secret validation safeguards (placeholder rejection in production).
7. Error response hardening (safe messages without traceback or credential leakage).
8. Upload size protection (chunked streaming rejection above MAX_FILE_SIZE).
9. Container non-root user verification and Docker security properties.
"""

import asyncio
import io
import json
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.services.document_service import DocumentService
from app.core.exceptions import FileValidationError


@pytest.mark.asyncio
class TestSecurityHeaders:
    """Verifies that security headers are emitted on responses."""

    async def test_standard_security_headers_present(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
            resp = await ac.get("/health")
            assert resp.status_code == 200
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"
            assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
            assert "X-Request-ID" in resp.headers


@pytest.mark.asyncio
class TestHostHeaderProtection:
    """Verifies Host header validation via TrustedHostMiddleware."""

    async def test_allowed_host_accepted(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
            resp = await ac.get("/health", headers={"Host": "localhost"})
            assert resp.status_code == 200

    async def test_untrusted_host_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://evil-attacker.com") as ac:
            resp = await ac.get("/health", headers={"Host": "evil-attacker.com"})
            assert resp.status_code == 400


class TestCORSAndConfigurationHardening:
    """Verifies CORS, cookie, debug, and secret validation safeguards."""

    def test_wildcard_cors_with_credentials_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                CORS_ORIGINS=["*"],
                POSTGRES_USER="test",
                POSTGRES_PASSWORD="test",
                POSTGRES_DB="test",
                POSTGRES_HOST="localhost",
            )
        assert "Wildcard '*' origin is forbidden" in str(exc_info.value)

    def test_production_with_debug_true_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DEBUG=True,
                SESSION_COOKIE_SECURE=True,
                SESSION_SECRET_KEY="a-very-long-production-secret-key-12345",
                POSTGRES_USER="test",
                POSTGRES_PASSWORD="test",
                POSTGRES_DB="test",
                POSTGRES_HOST="localhost",
            )
        assert "DEBUG must be False when ENVIRONMENT is 'production'" in str(exc_info.value)

    def test_production_insecure_cookie_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                DEBUG=False,
                SESSION_COOKIE_SECURE=False,
                SESSION_SECRET_KEY="a-very-long-production-secret-key-12345",
                POSTGRES_USER="test",
                POSTGRES_PASSWORD="test",
                POSTGRES_DB="test",
                POSTGRES_HOST="localhost",
            )
        assert "SESSION_COOKIE_SECURE must be True when DEBUG is False" in str(exc_info.value)

    def test_production_placeholder_secret_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DEBUG=False,
                SESSION_COOKIE_SECURE=True,
                SESSION_SECRET_KEY="change-me",
                POSTGRES_USER="test",
                POSTGRES_PASSWORD="test",
                POSTGRES_DB="test",
                POSTGRES_HOST="localhost",
            )
        assert "SESSION_SECRET_KEY cannot use default or known placeholder" in str(exc_info.value)


@pytest.mark.asyncio
class TestUploadSizeAndErrorHardening:
    """Verifies streaming upload size enforcement and safe error responses."""

    async def test_oversized_upload_rejected_early(self):
        from unittest.mock import AsyncMock
        mock_db = AsyncMock()
        mock_storage = AsyncMock()
        service = DocumentService(db=mock_db, storage=mock_storage)

        # Create a mock upload file simulating a stream exceeding MAX_FILE_SIZE
        mock_upload = AsyncMock()
        mock_upload.filename = "oversized_statement.pdf"

        # Stream 1MB chunks to quickly simulate exceeding 50MB
        chunk = b"%PDF-" + b"0" * (1024 * 1024)
        chunks = [chunk] * 52  # 52 MB > 50 MB
        chunks.append(b"")  # EOF sentinel

        read_iter = iter(chunks)

        async def mock_read(size=None):
            return next(read_iter)

        mock_upload.read.side_effect = mock_read

        with pytest.raises(FileValidationError) as exc_info:
            await service.validate_file(mock_upload)

        assert "exceeds maximum allowed size" in exc_info.value.message

    async def test_error_response_does_not_leak_internals_in_production(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
            # Hit a malformed endpoint or one triggering validation error
            resp = await ac.get("/api/v1/documents/chunks/invalid-uuid-format")
            assert resp.status_code in (400, 404, 422)
            content = resp.text
            # Verify no python tracebacks, filesystem paths, or credentials
            assert "Traceback" not in content
            assert "postgresql" not in content
            assert "password" not in content


class TestContainerSecurityProperties:
    """Static security verification of Dockerfiles and Compose configurations."""

    def test_backend_dockerfile_runs_as_non_root(self):
        with open("backend/Dockerfile", "r", encoding="utf-8") as f:
            content = f.read()
        assert "USER appuser" in content
        assert "groupadd" in content
        assert "useradd" in content

    def test_frontend_dockerfile_runs_as_non_root(self):
        with open("frontend/Dockerfile", "r", encoding="utf-8") as f:
            content = f.read()
        assert "USER nextjs" in content
        assert "addgroup" in content
        assert "adduser" in content

    def test_docker_compose_prod_no_privileged_containers(self):
        with open("docker-compose.prod.yml", "r", encoding="utf-8") as f:
            content = f.read()
        assert "privileged: true" not in content
