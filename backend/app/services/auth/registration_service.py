from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_token import EmailVerificationToken
from app.models.user import User
from app.utils.security import (
    generate_secure_token,
    hash_password,
    hash_token,
)


class EmailAlreadyRegisteredError(Exception):
    """Raised when an email address already belongs to an account."""


@dataclass(frozen=True)
class RegistrationResult:
    """
    Internal result of account registration.

    The raw verification token is provided only to the
    internal email-delivery layer. It must never be included
    in the public API response.
    """

    user: User
    verification_token: str


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
) -> RegistrationResult:
    """
    Create an unverified user account and its verification token.

    The user and token are persisted in a single transaction.
    """

    normalized_email = email.strip().casefold()

    existing_user = db.scalar(
        select(User).where(
            User.email_normalized == normalized_email
        )
    )

    if existing_user is not None:
        raise EmailAlreadyRegisteredError(
            "An account with this email address already exists"
        )

    raw_token = generate_secure_token()

    user = User(
        email=email,
        email_normalized=normalized_email,
        password_hash=hash_password(password),
        display_name=(
            display_name.strip()
            if display_name and display_name.strip()
            else None
        ),
    )

    verification_token = EmailVerificationToken(
        user=user,
        token_hash=hash_token(raw_token),
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(
                minutes=settings.email_verification_token_lifetime_minutes
            )
        ),
    )

    try:
        db.add(user)
        db.flush()

        db.add(verification_token)

        db.commit()

    except IntegrityError:
        db.rollback()

        # A concurrent registration may have inserted the
        # same normalized email after our initial lookup.
        existing_user = db.scalar(
            select(User).where(
                User.email_normalized == normalized_email
            )
        )

        if existing_user is not None:
            raise EmailAlreadyRegisteredError(
                "An account with this email address already exists"
            ) from None

        raise

    except Exception:
        db.rollback()
        raise

    return RegistrationResult(
        user=user,
        verification_token=raw_token,
    )
