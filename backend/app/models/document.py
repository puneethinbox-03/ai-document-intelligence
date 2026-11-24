from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Stores document metadata and ownership information.

    Original files are stored in private object storage.
    PostgreSQL stores the storage key, never a public file URL.

    Document processing lifecycle:
    Uploaded -> Validating -> Queued -> Processing -> Indexed

    Failure and deletion states:
    Failed, Deleting, Deleted
    """

    __tablename__ = "documents"

    # Owner of this document.
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    # Filename supplied by the user, retained as metadata.
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Private object-storage key, not a publicly accessible URL.
    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    # Validated media type, for example application/pdf.
    content_type: Mapped[str] = mapped_column(
        String(127),
        nullable=False,
    )

    # Original file size in bytes.
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    # Optional SHA-256 checksum for integrity and duplicate detection.
    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Lifecycle status, enforced by application logic.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="uploaded",
        server_default="uploaded",
    )

    # Sanitized error category; never store document contents or secrets.
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Safe user-facing processing error message, if applicable.
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
