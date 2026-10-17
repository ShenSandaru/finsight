import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import generate_session_token, hash_session_token, calculate_session_expiry
from app.main import app
from app.models.user import User, UserSession
from app.services.auth_service import (
    AuthService,
    generate_oauth_state,
    register_google_oauth,
    oauth,
)

settings = get_settings()


@pytest.mark.asyncio
async def test_auth_me_unauthenticated_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_auth_me_with_invalid_cookie_returns_401(db_session_factory):
    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.cookies.set(settings.SESSION_COOKIE_NAME, "non_existent_opaque_token")
            response = await ac.get("/api/v1/auth/me")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_session_middleware_registered():
    """Verify that Starlette SessionMiddleware is registered with secure settings."""
    from starlette.middleware.sessions import SessionMiddleware

    middleware_classes = [m.cls for m in app.user_middleware]
    assert SessionMiddleware in middleware_classes, "SessionMiddleware must be registered in app.user_middleware"

    session_mw = next(m for m in app.user_middleware if m.cls == SessionMiddleware)
    assert session_mw.kwargs["same_site"] == "lax"
    assert session_mw.kwargs["secret_key"] == settings.SESSION_SECRET_KEY
    assert session_mw.kwargs["session_cookie"] == "session"
    # Ensure SessionMiddleware cookie does not collide with user session cookie
    assert session_mw.kwargs["session_cookie"] != settings.SESSION_COOKIE_NAME


@pytest.mark.asyncio
async def test_google_login_exercises_real_session_middleware():
    """Verify that the OAuth login route executes Authlib's real save_authorize_data
    and populates request.session through Starlette SessionMiddleware without raising
    AssertionError: SessionMiddleware must be installed to access request.session.
    """
    register_google_oauth()
    mock_auth_url_result = {
        "url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=test_client&redirect_uri=http%3A%2F%2Ftest%2Fcallback&state=mock_state&nonce=mock_nonce",
        "state": "mock_state",
        "nonce": "mock_nonce",
    }
    # Mock only external URL generation, allowing real authorize_redirect and save_authorize_data to execute
    with patch.object(oauth.google, "create_authorization_url", AsyncMock(return_value=mock_auth_url_result)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/auth/google/login", follow_redirects=False)

        assert response.status_code == 302
        assert "accounts.google.com" in response.headers["location"]
        # FinSight's cryptographic HMAC state cookie
        assert settings.OAUTH_STATE_COOKIE_NAME in response.headers.get("set-cookie", "")
        # Starlette SessionMiddleware signed session cookie set by Authlib save_authorize_data
        assert "session=" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_missing_oauth_credentials_handled_safely():
    """Verify that unconfigured OAuth credentials produce valid redirect without leaking secrets."""
    register_google_oauth()
    mock_auth_url_result = {
        "url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=&redirect_uri=http%3A%2F%2Ftest%2Fcallback&state=mock_state",
        "state": "mock_state",
    }
    with patch.object(oauth.google, "create_authorization_url", AsyncMock(return_value=mock_auth_url_result)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/auth/google/login", follow_redirects=False)

        assert response.status_code == 302
        # Secret values must never appear in query params or response headers
        assert "secret" not in response.headers["location"].lower()


@pytest.mark.asyncio
async def test_google_callback_missing_state():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/google/callback?code=fake_code")
    assert response.status_code == 400
    assert "state" in response.text.lower()


@pytest.mark.asyncio
async def test_google_callback_tampered_state():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.cookies.set(settings.OAUTH_STATE_COOKIE_NAME, "valid_binding_format")
        response = await ac.get("/api/v1/auth/google/callback?code=fake_code&state=invalid_tampered_state")
    assert response.status_code == 400
    assert "state" in response.text.lower()


@pytest.mark.asyncio
async def test_google_callback_mismatched_or_cross_browser_cookie():
    state, cookie_binding = generate_oauth_state()
    _, different_cookie_binding = generate_oauth_state()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Browser B has a different cookie
        ac.cookies.set(settings.OAUTH_STATE_COOKIE_NAME, different_cookie_binding)
        response = await ac.get(f"/api/v1/auth/google/callback?code=fake_code&state={state}")
    assert response.status_code == 400
    assert "state" in response.text.lower()


@pytest.mark.asyncio
async def test_google_callback_error_query_param():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/google/callback?error=access_denied")
    assert response.status_code == 400
    assert "access_denied" in response.text


@pytest.mark.asyncio
async def test_oauth_state_unit_validation():
    from app.services.auth_service import validate_oauth_state
    import time

    state1, cookie1 = generate_oauth_state()
    state2, cookie2 = generate_oauth_state()

    # 1. Valid state and matching cookie succeeds
    assert validate_oauth_state(state1, cookie1, max_age_seconds=300) is True

    # 2. Missing state or cookie fails
    assert validate_oauth_state(None, cookie1) is False
    assert validate_oauth_state("", cookie1) is False
    assert validate_oauth_state(state1, None) is False
    assert validate_oauth_state(state1, "") is False

    # 3. Tampered state fails
    parts = state1.split(":")
    tampered_state = f"{parts[0]}:{parts[1]}:bad_sig"
    assert validate_oauth_state(tampered_state, cookie1) is False

    # 4. State from another browser/session fails
    assert validate_oauth_state(state1, cookie2) is False
    assert validate_oauth_state(state2, cookie1) is False

    # 5. Expired state fails
    assert validate_oauth_state(state1, cookie1, max_age_seconds=-1) is False

    # 6. Simultaneous flows have distinct states and do not interfere
    assert state1 != state2
    assert cookie1 != cookie2
    assert validate_oauth_state(state1, cookie1) is True
    assert validate_oauth_state(state2, cookie2) is True


@pytest.mark.asyncio
async def test_google_callback_valid_state_consumes_cookie_and_succeeds(db_session_factory):
    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        register_google_oauth()
        state, cookie_binding = generate_oauth_state()

        fake_token = {
            "access_token": "mock_access_token",
            "id_token": "mock_id_token",
            "userinfo": {
                "sub": f"google_test_sub_{uuid.uuid4().hex[:8]}",
                "email": "user@example.com",
                "name": "Test User",
                "picture": "https://example.com/avatar.jpg",
            },
        }

        with patch.object(oauth.google, "authorize_access_token", AsyncMock(return_value=fake_token)):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                ac.cookies.set(settings.OAUTH_STATE_COOKIE_NAME, cookie_binding)

                # First callback succeeds
                response = await ac.get(
                    f"/api/v1/auth/google/callback?code=mock_code&state={state}",
                    follow_redirects=False,
                )
                assert response.status_code == 302
                assert "/documents" in response.headers["location"]
                assert settings.SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")

                # Verify state cookie is cleared/consumed on redirect response
                set_cookie_header = response.headers.get("set-cookie", "")
                assert settings.OAUTH_STATE_COOKIE_NAME in set_cookie_header

                # Attempting to replay callback without the cookie fails (cookie consumed/deleted)
                ac.cookies.delete(settings.OAUTH_STATE_COOKIE_NAME)
                replay_no_cookie = await ac.get(
                    f"/api/v1/auth/google/callback?code=mock_code&state={state}",
                    follow_redirects=False,
                )
                assert replay_no_cookie.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_auth_logout_clears_cookie():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.cookies.set(settings.SESSION_COOKIE_NAME, "mock_token")
        response = await ac.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert settings.SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")
