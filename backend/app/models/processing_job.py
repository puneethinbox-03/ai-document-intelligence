from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentProcessingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Tracks background document processing jobs.

    Job status is separate from document lifecycle status.
    Retry scheduling and execution details are stored here.
    """

    __tablename__ = "document_processing_jobs"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
    )

    # Initial job state.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
    )

    # Number of processing attempts made so far.
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Maximum number of permitted processing attempts.
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )

    # Earliest time the worker may execute or retry this job.
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Sanitized error information; never store document content or secrets.
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
