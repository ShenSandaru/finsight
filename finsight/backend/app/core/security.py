import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def generate_session_token() -> str:
    """Generate a cryptographically secure opaque session token (32 bytes URL-safe)."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash an opaque session token with SHA-256 for secure database lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def calculate_session_expiry(max_age_seconds: int) -> datetime:
    "Calculate expiration timestamp given lifetime in seconds."
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=max_age_seconds)


def is_session_expired(expires_at: datetime) -> bool:
    "Check whether a session's expiration timestamp has passed."
    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    return current_time >= expires_at
