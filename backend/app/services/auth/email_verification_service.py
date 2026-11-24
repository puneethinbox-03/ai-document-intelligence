from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import EmailVerificationToken, User
from app.utils.security import hash_token


class InvalidVerificationTokenError(Exception):
    """Raised when an email verification token is invalid or unusable."""


def verify_email(db: Session, *, raw_token: str) -> User:
    """
    Verify a user's email address using a one-time verification token.

    The raw token is hashed before lookup. Successful verification
    consumes all outstanding verification tokens for that user.
    """

    if not isinstance(raw_token, str) or not raw_token:
        raise InvalidVerificationTokenError(
            "The verification link is invalid or has expired"
        )

    token_hash = hash_token(raw_token)

    try:
        verification_token = db.scalar(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token_hash == token_hash)
            .with_for_update()
        )

        now = datetime.now(timezone.utc)

        if (
            verification_token is None
            or verification_token.used_at is not None
            or verification_token.expires_at <= now
        ):
            raise InvalidVerificationTokenError(
                "The verification link is invalid or has expired"
            )

        user = verification_token.user

        if not user.is_active:
            raise InvalidVerificationTokenError(
                "The verification link is invalid or has expired"
            )

        if user.email_verified_at is None:
            user.email_verified_at = now

        # Update the loaded object as well as the database rows.
        verification_token.used_at = now

        # Consume every outstanding verification token for this user.
        db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        db.commit()

        return user

    except InvalidVerificationTokenError:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise
