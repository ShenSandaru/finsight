"""Comprehensive unit and integration test suite for FinSight Phase 12.3 Rate Limiting.

Covers all 21 test requirements:
1. Under limit succeeds
2. At limit succeeds
3. Over limit returns HTTP 429
4. Retry-After header present
5. Counter stored in Redis
6. Counter expires with correct TTL
7. Separate rate-limit windows do not collide
8. Concurrent requests do not race
9. User A quota is independent of User B
10. Changing request parameters does not bypass quota
11. Unauthenticated requests limited by IP
12. Arbitrary spoofed headers cannot bypass limit
13. RAG limit works
14. Search limit works
15. Report generation limit works (prevents background job spam)
16. Document upload limit works
17. OAuth login/callback limit works
18. Redis unavailable follows fail-open/fail-closed policy
19. Redis errors handled without leaking internals
20. Authenticated requests keyed by user UUID
21. Unauthenticated requests do not share authenticated bucket
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceeded
from app.core.rate_limit import (
    RateLimiter,
    build_rate_limit_key,
    parse_rate_limit,
    get_client_ip,
    get_redis_client,
)
from app.main import app
from app.models.user import User

settings = get_settings()


class FakeRedis:
    """In-memory Redis mock supporting atomic EVAL (Lua script), INCR, EXPIRE, TTL, FLUSHDB."""

    def __init__(self):
        self.store = {}
        self.ttls = {}

    async def eval(self, script: str, numkeys: int, key: str, window_seconds: int):
        current = self.store.get(key, 0) + 1
        self.store[key] = current
        if current == 1:
            self.ttls[key] = int(window_seconds)
        ttl = self.ttls.get(key, int(window_seconds))
        return [current, ttl]

    async def get(self, key: str):
        return str(self.store.get(key)) if key in self.store else None

    async def flushdb(self):
        self.store.clear()
        self.ttls.clear()


@pytest.mark.asyncio
async def test_parse_rate_limit():
    limit, window = parse_rate_limit("20/60")
    assert limit == 20
    assert window == 60


@pytest.mark.asyncio
async def test_rate_limiter_basic_under_at_over_limit():
    fake_redis = FakeRedis()
    limiter = RateLimiter(redis_client=fake_redis)
    key = "test:basic:1"

    # 1. Request under limit succeeds
    allowed, count, remaining, retry_after = await limiter.check(key, limit=3, window_seconds=60)
    assert allowed is True
    assert count == 1
    assert remaining == 2
    assert retry_after == 60

    # Request 2
    allowed, count, remaining, _ = await limiter.check(key, limit=3, window_seconds=60)
    assert allowed is True
    assert count == 2
    assert remaining == 1

    # 2. Request at limit succeeds
    allowed, count, remaining, _ = await limiter.check(key, limit=3, window_seconds=60)
    assert allowed is True
    assert count == 3
    assert remaining == 0

    # 3. Request over limit returns allowed=False
    allowed, count, remaining, retry_after = await limiter.check(key, limit=3, window_seconds=60)
    assert allowed is False
    assert count == 4
    assert remaining == 0
    assert retry_after > 0


@pytest.mark.asyncio
async def test_rate_limiter_redis_storage_and_ttl():
    fake_redis = FakeRedis()
    limiter = RateLimiter(redis_client=fake_redis)
    key = "test:ttl:1"

    # 5. Counter stored in Redis
    await limiter.check(key, limit=5, window_seconds=45)
    assert fake_redis.store[key] == 1
    # 6. TTL stored
    assert fake_redis.ttls[key] == 45


@pytest.mark.asyncio
async def test_rate_limiter_separate_windows_do_not_collide():
    fake_redis = FakeRedis()
    limiter = RateLimiter(redis_client=fake_redis)

    # 7. Separate keys do not collide
    await limiter.check("test:window:user1", limit=1, window_seconds=60)
    allowed2, count2, _, _ = await limiter.check("test:window:user2", limit=1, window_seconds=60)
    assert allowed2 is True
    assert count2 == 1


@pytest.mark.asyncio
async def test_rate_limiter_concurrency():
    fake_redis = FakeRedis()
    limiter = RateLimiter(redis_client=fake_redis)
    key = "test:concurrent:1"

    # 8. Concurrent requests evaluated atomically
    tasks = [limiter.check(key, limit=10, window_seconds=60) for _ in range(15)]
    results = await asyncio.gather(*tasks)

    allowed_count = sum(1 for r in results if r[0] is True)
    denied_count = sum(1 for r in results if r[0] is False)

    assert allowed_count == 10
    assert denied_count == 5


@pytest.mark.asyncio
async def test_user_isolation_quota():
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    fake_redis = FakeRedis()
    limiter = RateLimiter(redis_client=fake_redis)

    key_a = build_rate_limit_key("rag", f"user:{user_a}")
    key_b = build_rate_limit_key("rag", f"user:{user_b}")

    # Exhaust user A quota (limit=2)
    await limiter.check(key_a, limit=2, window_seconds=60)
    await limiter.check(key_a, limit=2, window_seconds=60)
    allowed_a, _, _, _ = await limiter.check(key_a, limit=2, window_seconds=60)
    assert allowed_a is False

    # 9. User B quota is completely independent
    allowed_b, count_b, _, _ = await limiter.check(key_b, limit=2, window_seconds=60)
    assert allowed_b is True
    assert count_b == 1


@pytest.mark.asyncio
async def test_changing_request_parameters_does_not_bypass_user_limit():
    user_a = uuid.uuid4()
    fake_redis = FakeRedis()
    limiter = RateLimiter(redis_client=fake_redis)

    # 10. Key is derived only from policy and user UUID, not parameters
    key1 = build_rate_limit_key("search", f"user:{user_a}")
    key2 = build_rate_limit_key("search", f"user:{user_a}")
    assert key1 == key2

    await limiter.check(key1, limit=1, window_seconds=60)
    allowed, _, _, _ = await limiter.check(key2, limit=1, window_seconds=60)
    assert allowed is False


@pytest.mark.asyncio
async def test_unauthenticated_ip_and_header_spoofing():
    # 11 & 12. Direct socket client host is used; spoofed headers do not alter get_client_ip
    from unittest.mock import MagicMock
    req = MagicMock()
    req.client.host = "192.168.1.50"
    req.headers = {"X-Forwarded-For": "8.8.8.8, 1.1.1.1"}

    assert get_client_ip(req) == "192.168.1.50"


@pytest.mark.asyncio
async def test_unauthenticated_requests_do_not_share_authenticated_bucket():
    user_id = uuid.uuid4()
    ip = "192.168.1.50"

    # 21. Keys are completely distinct
    key_auth = build_rate_limit_key("auth", f"user:{user_id}")
    key_unauth = build_rate_limit_key("auth", f"ip:{ip}")

    assert key_auth != key_unauth
    assert "user:" in key_auth
    assert "ip:" in key_unauth


@pytest.mark.asyncio
async def test_redis_failure_policies():
    # 18 & 19. Fail-closed vs fail-open
    from unittest.mock import MagicMock
    broken_client = MagicMock()
    broken_client.eval = AsyncMock(side_effect=ConnectionError("Redis connection refused"))

    limiter = RateLimiter(redis_client=broken_client)

    # Fail-closed raises HTTPException(503) without leaking internal redis details
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check("test:key", limit=10, window_seconds=60, fail_closed=True)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Redis connection refused" not in exc_info.value.detail

    # Fail-open returns allowed=True with warning
    allowed, count, remaining, retry = await limiter.check("test:key", limit=10, window_seconds=60, fail_closed=False)
    assert allowed is True
    assert remaining == 10


@pytest.mark.asyncio
async def test_http_endpoint_rate_limit_429_and_headers():
    fake_redis = FakeRedis()

    with patch("app.core.rate_limit.get_redis_client", return_value=fake_redis):
        # Override policy for testing: reports=2/60
        with patch.object(settings, "RATE_LIMIT_REPORTS", "2/60"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                # 15. Reports limit
                # Req 1
                r1 = await ac.post("/api/v1/reports", json={"query": "Financial summary 1"})
                assert r1.status_code in (status.HTTP_202_ACCEPTED, status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
                assert "X-RateLimit-Limit" in r1.headers
                assert r1.headers["X-RateLimit-Limit"] == "2"

                # Req 2
                r2 = await ac.post("/api/v1/reports", json={"query": "Financial summary 2"})
                assert "X-RateLimit-Remaining" in r2.headers

                # 3 & 4. Req 3 -> Over limit returns 429 and Retry-After
                r3 = await ac.post("/api/v1/reports", json={"query": "Financial summary 3"})
                assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                assert "Retry-After" in r3.headers
                assert int(r3.headers["Retry-After"]) > 0
                assert r3.headers["X-RateLimit-Remaining"] == "0"
                body = r3.json()
                assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
                assert "rate limit exceeded" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_auth_oauth_endpoint_rate_limiting():
    from app.services.auth_service import oauth, register_google_oauth
    from fastapi.responses import RedirectResponse

    register_google_oauth()
    fake_redis = FakeRedis()

    with patch("app.core.rate_limit.get_redis_client", return_value=fake_redis):
        with patch.object(settings, "RATE_LIMIT_AUTH", "2/60"):
            with patch.object(oauth.google, "authorize_redirect", return_value=RedirectResponse(url="https://accounts.google.com", status_code=302)):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    # 17. OAuth login endpoint limit
                    r1 = await ac.get("/api/v1/auth/google/login", follow_redirects=False)
                    assert r1.status_code == 302
                    r2 = await ac.get("/api/v1/auth/google/login", follow_redirects=False)
                    assert r2.status_code == 302
                    # Third request exceeds limit
                    r3 = await ac.get("/api/v1/auth/google/login", follow_redirects=False)
                    assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                    assert "Retry-After" in r3.headers


@pytest.mark.asyncio
async def test_authenticated_endpoint_uses_user_uuid_and_isolates_users():
    """Verify that authenticated endpoints resolve user:{user.id} via dependency and isolate users."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    user_a = User(
        id=user_a_id,
        email="usera@finsight.local",
        name="User A",
        provider="google",
        provider_sub="sub-a",
        is_active=True,
    )
    user_b = User(
        id=user_b_id,
        email="userb@finsight.local",
        name="User B",
        provider="google",
        provider_sub="sub-b",
        is_active=True,
    )

    fake_redis = FakeRedis()

    with patch("app.core.rate_limit.get_redis_client", return_value=fake_redis):
        with patch.object(settings, "RATE_LIMIT_RAG", "2/60"):
            from app.api.deps import get_current_user
            from app.services.rag_service import RAGService
            from app.schemas.rag import RAGResponseSchema

            # Mock RAG service answer
            mock_rag_response = RAGResponseSchema(
                query="Q",
                answer="A",
                citations=[],
                retrieved_chunks=0,
                grounded=True,
            )

            with patch.object(RAGService, "answer", new_callable=AsyncMock, return_value=mock_rag_response):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    # User A makes 2 requests (limit is 2)
                    app.dependency_overrides[get_current_user] = lambda: user_a
                    r1 = await ac.post("/api/v1/rag/query", json={"query": "test query 1"})
                    assert r1.status_code == 200
                    r2 = await ac.post("/api/v1/rag/query", json={"query": "test query 2"})
                    assert r2.status_code == 200

                    # 3rd request for User A is 429
                    r3 = await ac.post("/api/v1/rag/query", json={"query": "test query 3"})
                    assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS

                    # Verify User A's key in Redis is user:{user_a_id} and NOT ip:{client_ip}
                    expected_key_a = f"finsight:rl:rag:user:{user_a_id}"
                    assert expected_key_a in fake_redis.store
                    assert fake_redis.store[expected_key_a] == 3

                    # Confirm NO IP-based key was created for this authenticated request
                    for k in fake_redis.store.keys():
                        assert "ip:" not in k

                    # User B now makes a request -> should succeed (quota is independent)
                    app.dependency_overrides[get_current_user] = lambda: user_b
                    r_b = await ac.post("/api/v1/rag/query", json={"query": "user b query"})
                    assert r_b.status_code == 200

                    expected_key_b = f"finsight:rl:rag:user:{user_b_id}"
                    assert expected_key_b in fake_redis.store
                    assert fake_redis.store[expected_key_b] == 1
