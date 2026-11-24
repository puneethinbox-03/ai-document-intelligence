from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models import PasswordResetToken, User, UserSession
from app.utils.security import (
    generate_secure_token,
    hash_password,
    hash_token,
)


class InvalidPasswordResetTokenError(Exception):
    """Raised when a password-reset token is invalid or unusable."""


@dataclass(frozen=True)
class PasswordResetRequestResult:
    """
    Internal password-reset request result.

    The raw token must only be passed to the email-delivery layer.
    It must never be included in a public API response or logs.
    """

    reset_token: str


def request_password_reset(
    db: Session,
    *,
    email: str,
) -> PasswordResetRequestResult | None:
    """
    Create a password-reset token for an active account.

    Returns None when no active account matches the email.
    The API layer must return the same public response in either case.
    """

    normalized_email = email.strip().casefold()

    try:
        user = db.scalar(
            select(User).where(
                User.email_normalized == normalized_email,
                User.is_active.is_(True),
            )
        )

        if user is None:
            return None

        now = datetime.now(timezone.utc)

        # Invalidate previous unused reset tokens for this user.
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        raw_token = generate_secure_token()

        reset_token = PasswordResetToken(
            user=user,
            token_hash=hash_token(raw_token),
            expires_at=(
                now
                + timedelta(
                    minutes=settings.password_reset_token_lifetime_minutes
                )
            ),
        )

        db.add(reset_token)
        db.commit()

        return PasswordResetRequestResult(reset_token=raw_token)

    except Exception:
        db.rollback()
        raise


def reset_password(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
) -> User:
    """
    Consume a valid reset token and update the user's password.

    All existing sessions are revoked after a successful password reset.
    """

    if not isinstance(raw_token, str) or not raw_token:
        raise InvalidPasswordResetTokenError(
            "The password-reset link is invalid or has expired"
        )

    if not isinstance(new_password, str) or not new_password:
        raise ValueError("A non-empty password is required")

    token_hash = hash_token(raw_token)

    try:
        reset_token = db.scalar(
            select(PasswordResetToken)
            .options(joinedload(PasswordResetToken.user))
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
        )

        now = datetime.now(timezone.utc)

        if (
            reset_token is None
            or reset_token.used_at is not None
            or reset_token.revoked_at is not None
            or reset_token.expires_at <= now
        ):
            raise InvalidPasswordResetTokenError(
                "The password-reset link is invalid or has expired"
            )

        user = reset_token.user

        if user is None or not user.is_active:
            raise InvalidPasswordResetTokenError(
                "The password-reset link is invalid or has expired"
            )

        user.password_hash = hash_password(new_password)
        reset_token.used_at = now

        # Revoke every active session so the old password cannot
        # continue to be used through an existing browser session.
        db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        # Invalidate any other outstanding password-reset tokens.
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != reset_token.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        db.commit()

        return user

    except InvalidPasswordResetTokenError:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
