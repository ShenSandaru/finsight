"""Redis-backed distributed rate limiting and abuse protection for FinSight (Phase 12.3)."""

import asyncio
import logging
import time
from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceeded
from app.models.user import User

logger = logging.getLogger("finsight.rate_limit")
settings = get_settings()

# Atomic Lua script for fixed-window rate limiting:
# 1. INCR key
# 2. If first request (val == 1), set expiration
# 3. Fetch TTL in seconds (or -1 if none)
# Returns: {current_count, ttl_seconds}
_RATE_LIMIT_LUA_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""

_redis_client: Optional[aioredis.Redis] = None
_redis_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_redis_client() -> aioredis.Redis:
    """Return or initialize the aioredis client connected to REDIS_HOST:REDIS_PORT.

    Safely handles event loop transitions in testing and worker threads.
    """
    global _redis_client, _redis_client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _redis_client is not None:
        if _redis_client_loop != current_loop or (_redis_client_loop and _redis_client_loop.is_closed()):
            _redis_client = None

    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        _redis_client_loop = current_loop
    return _redis_client


async def close_rate_limit_redis() -> None:
    """Close the rate limit Redis client on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception as exc:
            logger.debug("Error closing rate limit Redis client: %s", exc)
        _redis_client = None


def parse_rate_limit(policy_str: str) -> tuple[int, int]:
    """Parse 'requests/window_seconds' e.g. '20/60' into (limit, window_seconds)."""
    parts = policy_str.strip().split("/")
    return int(parts[0]), int(parts[1])


def get_client_ip(request: Request) -> str:
    """Extract client IP address safely.

    Prioritizes request.client.host (the direct network peer socket).
    Does NOT blindly trust arbitrary user-controlled headers like X-Forwarded-For.
    """
    if request.client and request.client.host:
        return request.client.host
    return "unknown_client"


def build_rate_limit_key(policy_name: str, identity: str) -> str:
    """Construct namespaced Redis rate limit key."""
    return f"finsight:rl:{policy_name}:{identity}"


class RateLimiter:
    """Core rate limiting coordinator executing atomic Redis counter operations."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._client = redis_client

    @property
    def client(self) -> aioredis.Redis:
        return self._client or get_redis_client()

    async def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        fail_closed: bool = True,
    ) -> tuple[bool, int, int, int]:
        """Check and increment the rate limit for a given key.

        Returns:
            (allowed: bool, current_count: int, remaining: int, retry_after: int)
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True, 1, limit - 1, 0

        try:
            res = await self.client.eval(
                _RATE_LIMIT_LUA_SCRIPT,
                1,
                key,
                window_seconds,
            )
            current_count = int(res[0])
            ttl = int(res[1])
            retry_after = max(1, ttl) if ttl > 0 else window_seconds
            remaining = max(0, limit - current_count)
            allowed = current_count <= limit
            return allowed, current_count, remaining, retry_after

        except Exception as exc:
            logger.error("Redis error in rate limiter for key '%s': %s", key, exc)
            if fail_closed:
                # Sensitive endpoint: fail-closed to prevent abuse amplification during Redis outage
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiting service temporarily unavailable",
                ) from exc
            else:
                # Normal read endpoint: fail-open so user operations are not catastrophically blocked
                logger.warning("Failing open for rate limit key '%s'", key)
                return True, 0, limit, 0


def rate_limit(
    policy_name: str,
    fail_closed: bool = True,
    authenticated: bool = True,
) -> Callable:
    """FastAPI Dependency factory creating endpoint rate limiters.

    If authenticated=True (default), explicitly resolves the active User via get_current_user
    sub-dependency, ensuring user:{user.id} is guaranteed before quota consumption.
    If authenticated=False (e.g. unauthenticated OAuth endpoints), uses direct socket client IP ip:{client_ip}.
    """
    if authenticated:
        from app.api.deps import get_current_user

        async def auth_dependency(
            request: Request,
            response: Response,
            user: User = Depends(get_current_user),
        ):
            await _evaluate_rate_limit(request, response, policy_name, fail_closed, user=user)

        return auth_dependency
    else:
        async def ip_dependency(
            request: Request,
            response: Response,
        ):
            await _evaluate_rate_limit(request, response, policy_name, fail_closed, user=None)

        return ip_dependency


async def _evaluate_rate_limit(
    request: Request,
    response: Response,
    policy_name: str,
    fail_closed: bool,
    user: Optional[User] = None,
) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    # Retrieve policy configuration dynamically from Settings
    setting_attr = f"RATE_LIMIT_{policy_name.upper()}"
    policy_val = getattr(settings, setting_attr, None) or settings.RATE_LIMIT_GENERAL
    limit, window = parse_rate_limit(policy_val)

    # Resolve identity
    if user and getattr(user, "id", None):
        identity = f"user:{user.id}"
    else:
        # Fallback for unauthenticated requests: rate limit by client IP
        client_ip = get_client_ip(request)
        identity = f"ip:{client_ip}"

    key = build_rate_limit_key(policy_name, identity)
    limiter = RateLimiter()

    allowed, count, remaining, retry_after = await limiter.check(
        key=key,
        limit=limit,
        window_seconds=window,
        fail_closed=fail_closed,
    )

    reset_timestamp = int(time.time()) + retry_after

    # Attach standard rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_timestamp)

    if not allowed:
        logger.warning(
            "Rate limit exceeded: policy=%s identity=%s count=%d limit=%d retry_after=%ds endpoint=%s",
            policy_name,
            identity,
            count,
            limit,
            retry_after,
            request.url.path,
        )
        response.headers["Retry-After"] = str(retry_after)
        raise RateLimitExceeded(
            message=f"Rate limit exceeded for {policy_name}. Please try again in {retry_after} seconds.",
            retry_after=retry_after,
            limit=limit,
            window_seconds=window,
        )
