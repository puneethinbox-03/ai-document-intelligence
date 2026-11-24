from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Chat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chats"

    __table_args__ = (
        Index(
            "ix_chats_user_id_created_at",
            "user_id",
            "created_at",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Chat",
        server_default="New Chat",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="chats",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    document_associations: Mapped[list["ChatDocument"]] = relationship(
        "ChatDocument",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_documents"

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "document_id",
            name="uq_chat_documents_chat_document",
        ),
        Index(
            "ix_chat_documents_document_id",
            "document_id",
        ),
    )

    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="document_associations",
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chat_associations",
    )
