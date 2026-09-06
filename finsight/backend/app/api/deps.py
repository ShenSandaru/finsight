from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService

settings = get_settings()


async def get_current_user(
    finsight_session: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that extracts the HttpOnly session cookie, validates the session,

    and returns the authenticated active User.
    Raises 401 UNAUTHORIZED if missing, invalid, expired, or user is inactive.
    """
    if not finsight_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user = await AuthService.get_user_by_session_token(db, finsight_session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user


async def get_optional_user(
    finsight_session: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Dependency that extracts the session cookie if present and returns the active User,

    or returns None without raising 401.
    """
    if not finsight_session:
        return None

    return await AuthService.get_user_by_session_token(db, finsight_session)
