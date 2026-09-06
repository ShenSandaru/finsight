import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.services.auth_service import (
    AuthService,
    generate_oauth_state,
    oauth,
    register_google_oauth,
    validate_oauth_state,
)

from app.core.rate_limit import rate_limit

logger = logging.getLogger("finsight.api.auth")
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/google/login", dependencies=[Depends(rate_limit("auth", fail_closed=True, authenticated=False))])
async def google_login(request: Request, response: Response):
    """Initiate Google OAuth 2.0 / OIDC authorization flow.

    Generates a secure state parameter bound to an HttpOnly cookie to prevent login-CSRF
    and redirects the user to Google.
    """
    register_google_oauth()
    state, cookie_binding = generate_oauth_state()

    redirect_uri = settings.GOOGLE_REDIRECT_URI
    redirect_resp = await oauth.google.authorize_redirect(request, redirect_uri, state=state)
    redirect_resp.set_cookie(
        key=settings.OAUTH_STATE_COOKIE_NAME,
        value=cookie_binding,
        max_age=settings.OAUTH_STATE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )
    return redirect_resp


@router.get("/google/callback", dependencies=[Depends(rate_limit("auth", fail_closed=True, authenticated=False))])
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    oauth_state_cookie: Optional[str] = Cookie(default=None, alias=settings.OAUTH_STATE_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    """Handle the Google OAuth 2.0 authorization callback.

    Validates state parameter, exchanges code for tokens, extracts and verifies
    canonical Google `sub` identity, upserts User, creates a server-side session,
    and sets an HttpOnly cookie.
    """
    # Helper to clear state cookie on error responses
    def _error(status_code: int, detail: str) -> HTTPException:
        response.delete_cookie(
            key=settings.OAUTH_STATE_COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="lax",
            secure=settings.SESSION_COOKIE_SECURE,
        )
        return HTTPException(status_code=status_code, detail=detail)

    if error:
        logger.warning("Google OAuth callback returned error: %s", error)
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            f"Google OAuth error: {error}",
        )

    if not state or not oauth_state_cookie or not validate_oauth_state(state, oauth_state_cookie):
        logger.warning("Google OAuth callback received invalid, missing, or mismatched state/cookie")
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Invalid or expired OAuth state parameter",
        )

    if not code:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "Authorization code missing from Google callback",
        )

    register_google_oauth()

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        logger.error("Failed to exchange OAuth token with Google: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with Google",
        )

    # Validate OIDC ID Token & userinfo claims
    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = await oauth.google.userinfo(token=token)
        except Exception as exc:
            logger.error("Failed to fetch Google userinfo: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve Google user profile",
            )

    sub = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name") or email or "Google User"
    picture = userinfo.get("picture")

    if not sub or not email:
        logger.error("Google userinfo missing sub or email: sub=%s, email=%s", sub, email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google profile: missing required identity claims",
        )

    # Locate or create user by canonical (provider='google', provider_sub=sub)
    user = await AuthService.get_or_create_google_user(
        db=db,
        sub=sub,
        email=email,
        name=name,
        image_url=picture,
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Create server-side session
    _, raw_token = await AuthService.create_session(db=db, user_id=user.id)

    # Redirect to frontend with HttpOnly cookie and consume/clear OAuth state cookie
    redirect_target = f"{settings.FRONTEND_URL}/documents"
    redirect_resp = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)
    redirect_resp.delete_cookie(
        key=settings.OAUTH_STATE_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    redirect_resp.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )
    return redirect_resp


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Retrieve the currently authenticated user's profile."""
    return current_user


@router.post("/logout")
async def logout(
    response: Response,
    finsight_session: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    """Log out the current user, revoke the server-side session, and clear the session cookie."""
    if finsight_session:
        await AuthService.revoke_session(db, finsight_session)

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return {"message": "Successfully logged out"}
