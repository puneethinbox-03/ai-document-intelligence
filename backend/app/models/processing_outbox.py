from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentProcessingOutbox(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Durable dispatch instructions for document-processing jobs.

    PostgreSQL is the source of truth. Redis is only the delivery
    mechanism. A pending outbox record can be dispatched again
    if Redis is temporarily unavailable.
    """

    __tablename__ = "document_processing_outbox"

    __table_args__ = (
        CheckConstraint(
            "delivery_attempts >= 0",
            name="delivery_attempts_non_negative",
        ),
        Index(
            "ix_document_processing_outbox_available",
            "dispatched_at",
            "available_at",
            "lease_expires_at",
        ),
        Index(
            "ix_document_processing_outbox_processing_job_id",
            "processing_job_id",
        ),
    )

    processing_job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "document_processing_jobs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    dispatch_id: Mapped[UUID] = mapped_column(
        nullable=False,
        unique=True,
    )

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lease_token: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivery_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    processing_job: Mapped["DocumentProcessingJob"] = relationship(
        "DocumentProcessingJob",
    )
