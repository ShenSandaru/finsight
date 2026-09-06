import uuid
from datetime import datetime, timezone, timedelta

pytest = __import__("pytest")

from app.core.security import (
    generate_session_token,
    hash_session_token,
    calculate_session_expiry,
    is_session_expired,
)
from app.models.user import User, UserSession
from app.schemas.auth import UserResponse, AuthStatusResponse


def test_session_token_generation_and_hashing():
    token1 = generate_session_token()
    token2 = generate_session_token()

    assert isinstance(token1, str)
    assert isinstance(token2, str)
    assert len(token1) >= 32
    assert token1 != token2

    hash1 = hash_session_token(token1)
    hash2 = hash_session_token(token2)

    assert isinstance(hash1, str)
    assert len(hash1) == 64 # SHA-256 hex digest length
    assert hash1 == hash_session_token(token1)
    assert hash1 != hash2


def test_session_expiry_status():
    expiry_utc = calculate_session_expiry(3600)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    assert expiry_utc > now_utc
    assert not is_session_expired(expiry_utc)

    past_expiry = now_utc - timedelta(seconds=10)
    assert is_session_expired(past_expiry)


@pytest.mark.asyncio
async def test_user_and_session_models_instantiation():
    user = User(
        id=uuid.uuid4(),
        email="alice@example.com",
        name="Alice Smith",
        image_url="https://example.com/photo.jpg",
        provider="google",
        provider_sub="1234567890",
        is_active=True,
    )
    assert user.email == "alice@example.com"
    assert user.provider == "google"
    assert user.provider_sub == "1234567890"
    assert user.is_active is True
    assert "Alice" in repr(user)

    random_token = generate_session_token()
    token_hash = hash_session_token(random_token)
    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_token_hash=token_hash,
        expires_at=calculate_session_expiry(604800),
    )
    assert session.user_id == user.id
    assert session.session_token_hash == token_hash
    assert "user_id" in repr(session)


def test_pydantic_auth_schemas():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user_id = uuid.uuid4()
    resp = UserResponse(
        id=user_id,
        email="alice@example.com",
        name="Alice Smith",
        provider="google",
        provider_sub="987654321",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    assert resp.id == user_id
    assert resp.email == "alice@example.com"

    auth_status = AuthStatusResponse(is_authenticated=True, user=resp)
    assert auth_status.is_authenticated is True
    assert auth_status.user.email == "alice@example.com"


def test_production_cookie_security_validation():
    from app.core.config import Settings

    # 1. DEBUG=True + Secure=False -> allowed
    s1 = Settings(DEBUG=True, SESSION_COOKIE_SECURE=False)
    assert s1.SESSION_COOKIE_SECURE is False

    # 2. DEBUG=True + Secure=True -> allowed
    s2 = Settings(DEBUG=True, SESSION_COOKIE_SECURE=True)
    assert s2.SESSION_COOKIE_SECURE is True

    # 3. DEBUG=False + Secure=True -> allowed
    s3 = Settings(DEBUG=False, SESSION_COOKIE_SECURE=True)
    assert s3.SESSION_COOKIE_SECURE is True

    # 4. DEBUG=False + Secure=False -> rejected with ValueError
    with pytest.raises(ValueError, match="Insecure session cookie configuration"):
        Settings(DEBUG=False, SESSION_COOKIE_SECURE=False)
