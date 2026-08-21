"""Pytest configuration and environment fixtures."""

import os
import pytest

# Ensure tests running on host machine connect to localhost postgres if POSTGRES_HOST is not explicitly set to a reachable host
if os.environ.get("POSTGRES_HOST") is None:
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
