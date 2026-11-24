from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ------------------------------------------------------------
# Database naming conventions
# ------------------------------------------------------------

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# ------------------------------------------------------------
# SQLAlchemy declarative base
# ------------------------------------------------------------

class Base(DeclarativeBase):
    """
    Shared declarative base for all application database models.

    Centralizes metadata and database naming conventions.
    """

    metadata = MetaData(
        naming_convention=NAMING_CONVENTION
    )


# ------------------------------------------------------------
# UUID primary key mixin
# ------------------------------------------------------------

class UUIDPrimaryKeyMixin:
    """
    Provides a UUID primary key to database models.
    """

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


# ------------------------------------------------------------
# Timestamp mixin
# ------------------------------------------------------------

class TimestampMixin:
    """
    Provides common creation and update timestamps.

    Timestamps are timezone-aware and use the database clock.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
