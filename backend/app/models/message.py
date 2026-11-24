from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="role_valid",
        ),
        Index(
            "ix_messages_chat_id_created_at",
            "chat_id",
            "created_at",
        ),
    )

    chat_id: Mapped[UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages",
    )
