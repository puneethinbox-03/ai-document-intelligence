from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """
    Stores security and application audit events.

    Audit records are immutable. Metadata must contain only
    safe structured information, never document contents,
    prompts, responses, credentials, or authentication tokens.
    """

    __tablename__ = "audit_events"

    __table_args__ = (
        Index(
            "ix_audit_events_actor_user_id_created_at",
            "actor_user_id",
            "created_at",
        ),
        Index(
            "ix_audit_events_resource_type_resource_id",
            "resource_type",
            "resource_id",
        ),
    )

    # SET NULL preserves audit history when a user is deleted.
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Generic resource reference; intentionally has no foreign key.
    resource_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    # Safe structured metadata only.
    event_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    actor: Mapped["User | None"] = relationship(
        "User",
        back_populates="audit_events",
    )
