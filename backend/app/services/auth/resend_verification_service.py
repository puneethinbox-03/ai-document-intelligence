from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import EmailVerificationToken, User
from app.utils.security import generate_secure_token, hash_token


@dataclass(frozen=True)
class ResendVerificationResult:
    verification_token: str


def resend_verification_email(
    db: Session,
    *,
    email: str,
) -> ResendVerificationResult | None:
    """
    Create a replacement verification token for an eligible account.

    Return None for unknown, inactive, or already verified accounts
    so the public API can use a uniform response.
    """

    normalized_email = email.strip().casefold()

    try:
        user = db.scalar(
            select(User)
            .where(
                User.email_normalized == normalized_email,
                User.is_active.is_(True),
            )
            .with_for_update()
        )

        if (
            user is None
            or not user.is_active
            or user.email_verified_at is not None
        ):
            db.rollback()
            return None

        now = datetime.now(timezone.utc)

        # Invalidate all previous unused verification tokens.
        db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        raw_token = generate_secure_token()

        replacement_token = EmailVerificationToken(
            user=user,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(
                minutes=settings.email_verification_token_lifetime_minutes
            ),
        )

        db.add(replacement_token)
        db.commit()

        return ResendVerificationResult(
            verification_token=raw_token,
        )

    except Exception:
        db.rollback()
        raise
