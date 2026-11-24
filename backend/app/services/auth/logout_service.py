from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserSession
from app.utils.security import hash_token


def revoke_session(
    db: Session,
    *,
    raw_token: str,
) -> bool:
    """
    Revoke a session using its raw token.

    Returns True when an active session was revoked.
    Returns False when the token is missing, unknown,
    or the session was already revoked.
    """

    if not isinstance(raw_token, str) or not raw_token:
        return False

    token_hash = hash_token(raw_token)

    try:
        user_session = db.scalar(
            select(UserSession)
            .where(UserSession.token_hash == token_hash)
            .with_for_update()
        )

        if user_session is None or user_session.revoked_at is not None:
            db.rollback()
            return False

        user_session.revoked_at = datetime.now(timezone.utc)

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise
