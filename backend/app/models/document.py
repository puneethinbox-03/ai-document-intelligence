from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    __table_args__ = (
        UniqueConstraint(
            "storage_key",
            name="uq_documents_storage_key",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="file_size_positive",
        ),
        CheckConstraint(
            "status IN ('uploaded', 'validating', 'queued', "
            "'processing', 'indexed', 'failed', 'deleting', 'deleted')",
            name="status_valid",
        ),
        Index(
            "ix_documents_user_id_status",
            "user_id",
            "status",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(127),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="uploaded",
        server_default="uploaded",
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
    )

    chat_associations: Mapped[list["ChatDocument"]] = relationship(
        "ChatDocument",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    processing_jobs: Mapped[list["DocumentProcessingJob"]] = relationship(
        "DocumentProcessingJob",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
