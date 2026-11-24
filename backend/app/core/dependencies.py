import hmac
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User
from app.services.auth.session_service import (
    InvalidSessionError,
    get_authenticated_user,
)


def get_current_user(
    session_token: str | None = Cookie(
        default=None,
        alias=settings.session_cookie_name,
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate a request using its HttpOnly session cookie.

    The raw session token is validated against its stored
    SHA-256 hash. The authenticated user comes from the
    database session, never from request data.
    """

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        return get_authenticated_user(
            db,
            raw_token=session_token,
        )
    except InvalidSessionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid or has expired",
        ) from None


def require_csrf(
    request: Request,
    csrf_token_header: str | None = Header(
        default=None,
        alias="X-CSRF-Token",
    ),
    csrf_cookie: str | None = Cookie(
        default=None,
        alias=settings.csrf_cookie_name,
    ),
) -> None:
    """
    Validate Origin and the double-submit CSRF token.

    Use this dependency on state-changing browser endpoints
    authenticated through cookies.
    """

    if not settings.csrf_protection_enabled:
        return

    origin = request.headers.get("origin")

    if not origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin could not be verified",
        )

    # Require an exact origin: scheme, hostname and port.
    try:
        parsed_origin = urlsplit(origin)

        if (
            not parsed_origin.scheme
            or not parsed_origin.netloc
            or parsed_origin.path
            or parsed_origin.query
            or parsed_origin.fragment
            or parsed_origin.username
            or parsed_origin.password
        ):
            raise ValueError("Invalid origin")

        normalized_origin = (
            f"{parsed_origin.scheme}://{parsed_origin.netloc}"
        ).rstrip("/")

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin could not be verified",
        ) from None

    allowed_origins = {
        configured_origin.rstrip("/")
        for configured_origin in settings.cors_origins
    }

    allowed_origins.add(settings.frontend_url.rstrip("/"))

    if normalized_origin not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin is not allowed",
        )

    if not csrf_cookie or not csrf_token_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )

    if not hmac.compare_digest(csrf_cookie, csrf_token_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
