from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class UsageEvent(UUIDPrimaryKeyMixin, Base):
    """
    Records user-level application usage for analytics
    and future usage-limit enforcement.

    Usage events are immutable. Metadata must contain only
    safe structured information, never document contents,
    prompts, responses, credentials, or authentication tokens.
    """

    __tablename__ = "usage_events"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="duration_non_negative",
        ),
        Index(
            "ix_usage_events_user_id_created_at",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_usage_events_event_type_created_at",
            "event_type",
            "created_at",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Count or quantity associated with this usage event.
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    # Optional duration in milliseconds.
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Safe structured usage metadata only.
    event_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="usage_events",
    )
