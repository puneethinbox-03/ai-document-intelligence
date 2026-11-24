from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Stores a registered application user's account information.

    Passwords are stored only as secure password hashes.
    Email normalization and uniqueness are enforced by the application
    and database constraints added in a later implementation step.
    """

    __tablename__ = "users"

    # Original email value retained for account display.
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    # Normalized email used for consistent account lookup.
    email_normalized: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    # Encoded password hash (for example, an Argon2id hash).
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Optional name shown in the application.
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Set when the user successfully verifies their email address.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Allows an account to be deactivated without deleting its records.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
