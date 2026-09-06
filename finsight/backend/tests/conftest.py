"""Pytest configuration and environment fixtures."""

import os
os.environ["TESTING"] = "1"
import pytest

# Ensure environment variables are loaded from root .env if running tests from root or backend
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

# Ensure tests running on host machine connect to localhost postgres if POSTGRES_HOST is not explicitly set to a reachable host
if os.environ.get("POSTGRES_HOST") in (None, "postgres"):
    import socket
    try:
        socket.getaddrinfo("postgres", 5432)
    except socket.gaierror:
        # Running on host machine outside docker container -> point to localhost port mapped in docker-compose (5432)
        os.environ["POSTGRES_HOST"] = "localhost"
        os.environ["REDIS_HOST"] = "localhost"

from app.core.config import get_settings
get_settings.cache_clear()

from app.core.database import async_session
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import Request
from app.main import app
from app.api.deps import get_current_user
from app.models.user import User
import uuid

@pytest.fixture(autouse=True)
def default_authenticated_user(request):
    """
    By default, provide an authenticated system user for all legacy API tests so they don't fail with 401.
    Tests specifically targeting unauthenticated endpoints can add marker `pytest.mark.unauthenticated`
    or manage app.dependency_overrides directly.
    """
    if "unauthenticated" in request.keywords or "test_auth_routes" in request.module.__name__:
        yield None
    else:
        settings = get_settings()
        system_user = User(
            id=uuid.UUID(settings.SYSTEM_USER_ID),
            email="system@finsight.local",
            name="FinSight System",
            provider="system",
            provider_sub="system-default",
            is_active=True,
        )
        async def override_get_current_user(request: Request):
            request.state.current_user = system_user
            return system_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        try:
            yield system_user
        finally:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def db_session_factory():
    """Create a test async session factory with NullPool to prevent event loop connection sharing issues."""
    settings = get_settings()
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
    )
    test_async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return test_async_session


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Flush Redis rate-limiting keys between tests using sync client to avoid async fixture loop conflicts."""
    import redis
    settings = get_settings()
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        keys = r.keys("finsight:rl:*")
        if keys:
            r.delete(*keys)
        r.close()
    except Exception:
        pass
    yield
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        keys = r.keys("finsight:rl:*")
        if keys:
            r.delete(*keys)
        r.close()
    except Exception:
        pass
