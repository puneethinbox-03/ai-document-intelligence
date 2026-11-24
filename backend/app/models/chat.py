from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Chat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Stores a user's chat conversation metadata.

    A chat belongs to exactly one user.
    """

    __tablename__ = "chats"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Chat",
        server_default="New Chat",
    )


class ChatDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Associates documents with a chat conversation.

    This association determines which documents are selected
    as context for a particular chat.
    """

    __tablename__ = "chat_documents"

    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("chats.id"),
        nullable=False,
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
    )
