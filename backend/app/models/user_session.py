from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Stores server-managed authentication sessions.

    Only a cryptographic hash of the session token is stored.
    The raw session token must never be persisted in the database.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    # SHA-256 or another approved hash of the random session token.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Set when the session is explicitly invalidated.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Updated when the authenticated session is used.
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
