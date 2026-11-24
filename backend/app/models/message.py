from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Stores user and assistant messages within a chat.

    Source metadata supports RAG citations and document references.
    Message content and source metadata must not be written to logs.
    """

    __tablename__ = "messages"

    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("chats.id"),
        nullable=False,
    )

    # Supported initial roles: user and assistant.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Full message text. Do not log this content.
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Optional RAG source/citation metadata.
    # Example: document ID, page number, chunk ID and source label.
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
