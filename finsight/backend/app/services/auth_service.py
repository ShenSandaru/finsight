import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid

from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    generate_session_token,
    hash_session_token,
    calculate_session_expiry,
    is_session_expired,
)
from app.models.user import User, UserSession

logger = logging.getLogger("finsight.auth")
settings = get_settings()

oauth = OAuth()


def register_google_oauth():
    """Register Google OAuth with OpenID Connect discovery."""
    if "google" not in oauth._registry:
        oauth.register(
            name="google",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


def generate_oauth_state() -> Tuple[str, str]:
    """Generate a cryptographically random OAuth state token and its browser cookie binding.

    Returns:
        (state, cookie_binding):
            - state: sent to Google in authorization URL
            - cookie_binding: stored in ephemeral HttpOnly cookie on initiating browser
    """
    random_id = secrets.token_urlsafe(32)
    cookie_binding = secrets.token_urlsafe(32)
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    # Payload includes random_id, timestamp, and cookie_binding
    payload = f"{random_id}:{timestamp}:{cookie_binding}"
    signature = hashlib.sha256(f"{payload}:{settings.SESSION_SECRET_KEY}".encode("utf-8")).hexdigest()
    # State parameter sent to Google contains random_id, timestamp, and signature
    # (cookie_binding remains in browser cookie, protecting against external forgery)
    state = f"{random_id}:{timestamp}:{signature}"
    return state, cookie_binding


def validate_oauth_state(
    state_str: Optional[str],
    cookie_binding: Optional[str],
    max_age_seconds: int = 300,
) -> bool:
    """Validate that the OAuth state matches the initiating browser's cookie binding, signature, and TTL.

    Guarantees:
    1. Rejects missing state or missing cookie binding.
    2. Rejects states from a different browser session.
    3. Rejects tampered states.
    4. Rejects expired states (> max_age_seconds).
    """
    if not state_str or not cookie_binding or state_str.count(":") != 2:
        return False

    random_id, ts_str, sig = state_str.split(":")
    payload = f"{random_id}:{ts_str}:{cookie_binding}"
    expected_sig = hashlib.sha256(f"{payload}:{settings.SESSION_SECRET_KEY}".encode("utf-8")).hexdigest()

    if not secrets.compare_digest(sig, expected_sig):
        return False

    try:
        ts = int(ts_str)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if now_ts < ts or (now_ts - ts) > max_age_seconds:
            return False
    except Exception:
        return False

    return True


class AuthService:
    """Service handling User resolution, Server-Side Session management, and Google OIDC."""

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @staticmethod
    async def get_or_create_google_user(
        db: AsyncSession,
        sub: str,
        email: str,
        name: str,
        image_url: Optional[str] = None,
    ) -> User:
        """Locate existing user by (provider='google', provider_sub=sub), or create a new user."""
        stmt = select(User).where(User.provider == "google", User.provider_sub == sub)
        result = await db.execute(stmt)
        user = result.scalars().one_or_none()

        if user:
            # Update safe profile fields if changed
            updated = False
            if user.email != email:
                user.email = email
                updated = True
            if name and user.name != name:
                user.name = name
                updated = True
            if image_url and user.image_url != image_url:
                user.image_url = image_url
                updated = True
            if updated:
                user.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(user)
            return user

        # Create new user
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name or email,
            image_url=image_url,
            provider="google",
            provider_sub=sub,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created new Google authenticated user: %s", user.id)
        return user

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: uuid.UUID,
        max_age_seconds: Optional[int] = None,
    ) -> Tuple[UserSession, str]:
        """Generate a random opaque session token, hash it, and store in PostgreSQL."""
        if max_age_seconds is None:
            max_age_seconds = settings.SESSION_MAX_AGE_SECONDS

        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = calculate_session_expiry(max_age_seconds)

        session = UserSession(
            id=uuid.uuid4(),
            user_id=user_id,
            session_token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session, raw_token

    @staticmethod
    async def get_user_by_session_token(
        db: AsyncSession,
        raw_token: str,
    ) -> Optional[User]:
        """Look up opaque session token by SHA-256 hash and return the active User."""
        if not raw_token:
            return None

        token_hash = hash_session_token(raw_token)
        stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
        result = await db.execute(stmt)
        session = result.scalars().one_or_none()

        if not session:
            return None

        if is_session_expired(session.expires_at):
            await db.delete(session)
            await db.commit()
            return None

        user = await AuthService.get_user_by_id(db, session.user_id)
        if not user or not user.is_active:
            return None

        return user

    @staticmethod
    async def revoke_session(db: AsyncSession, raw_token: str) -> bool:
        """Delete session by raw token hash on logout."""
        if not raw_token:
            return False
        token_hash = hash_session_token(raw_token)
        stmt = select(UserSession).where(UserSession.session_token_hash == token_hash)
        result = await db.execute(stmt)
        session = result.scalars().one_or_none()
        if session:
            await db.delete(session)
            await db.commit()
            return True
        return False
