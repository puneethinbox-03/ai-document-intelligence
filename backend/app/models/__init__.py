"""Central registration point for all SQLAlchemy models."""

from app.models.base import Base
from app.models.user import User
from app.models.user_session import UserSession
from app.models.auth_token import (
    EmailVerificationToken,
    PasswordResetToken,
)
from app.models.document import Document
from app.models.chat import Chat, ChatDocument
from app.models.message import Message
from app.models.processing_job import DocumentProcessingJob
from app.models.audit_event import AuditEvent
from app.models.usage_event import UsageEvent

__all__ = [
    "Base",
    "User",
    "UserSession",
    "EmailVerificationToken",
    "PasswordResetToken",
    "Document",
    "Chat",
    "ChatDocument",
    "Message",
    "DocumentProcessingJob",
    "AuditEvent",
    "UsageEvent",
]
