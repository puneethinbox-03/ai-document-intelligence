from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, UserSession
from app.utils.security import (
    generate_secure_token,
    hash_token,
    verify_password,
)


class AuthenticationError(Exception):
    """Raised when authentication cannot be completed."""


@dataclass(frozen=True)
class LoginResult:
    """
    Internal login result.

    The raw session token must only be passed to the API layer
    for setting a secure HttpOnly cookie. Never return it in JSON.
    """

    user: User
    session_token: str
    expires_at: datetime


def login_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> LoginResult:
    """
    Authenticate a user and create a new database-backed session.
    """

    normalized_email = email.strip().casefold()

    try:
        user = db.scalar(
            select(User).where(
                User.email_normalized == normalized_email
            )
        )

        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active or user.email_verified_at is None:
            raise AuthenticationError("Invalid email or password")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(
            hours=settings.session_lifetime_hours
        )

        raw_session_token = generate_secure_token()

        user_session = UserSession(
            user=user,
            token_hash=hash_token(raw_session_token),
            expires_at=expires_at,
            last_used_at=now,
        )

        db.add(user_session)
        db.commit()

        return LoginResult(
            user=user,
            session_token=raw_session_token,
            expires_at=expires_at,
        )

    except AuthenticationError:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
