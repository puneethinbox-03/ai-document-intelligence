from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import User, UserSession
from app.utils.security import hash_token


class InvalidSessionError(Exception):
    """Raised when a session is invalid, expired, or revoked."""


def get_authenticated_user(
    db: Session,
    *,
    raw_token: str,
) -> User:
    """
    Validate a session token and return its associated user.

    Only the SHA-256 hash of the raw session token is used
    for database lookup. The raw token is never stored.
    """

    if not isinstance(raw_token, str) or not raw_token:
        raise InvalidSessionError("Your session is invalid or has expired")

    token_hash = hash_token(raw_token)

    try:
        user_session = db.scalar(
            select(UserSession)
            .options(joinedload(UserSession.user))
            .where(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(timezone.utc),
            )
        )

        if user_session is None:
            raise InvalidSessionError(
                "Your session is invalid or has expired"
            )

        user = user_session.user

        if (
            user is None
            or not user.is_active
            or user.email_verified_at is None
        ):
            raise InvalidSessionError(
                "Your session is invalid or has expired"
            )

        user_session.last_used_at = datetime.now(timezone.utc)
        db.commit()

        return user

    except InvalidSessionError:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
