from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class SampleModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sample_models"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )


class RelatedSampleModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "related_sample_models"

    sample_id: Mapped[UUID] = mapped_column(
        ForeignKey("sample_models.id"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("code"),
    )


def test_base_uses_shared_metadata():
    """Verify that models inherit the shared declarative metadata."""

    assert SampleModel.metadata is Base.metadata
    assert RelatedSampleModel.metadata is Base.metadata

    assert "sample_models" in Base.metadata.tables
    assert "related_sample_models" in Base.metadata.tables


def test_uuid_primary_key_configuration():
    """Verify that the UUID primary key is configured correctly."""

    column = SampleModel.__table__.c.id

    assert column.primary_key is True
    assert column.type.as_uuid is True
    assert column.default is not None


def test_timestamp_configuration():
    """Verify timezone-aware database timestamp defaults."""

    table = SampleModel.__table__

    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False

    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    assert table.c.created_at.server_default is not None
    assert table.c.updated_at.server_default is not None
    assert table.c.updated_at.onupdate is not None


def test_index_naming_convention():
    """Verify automatically generated index names."""

    table = SampleModel.__table__

    index_names = {
        index.name
        for index in table.indexes
    }

    assert "ix_sample_models_name" in index_names


def test_primary_key_naming_convention():
    """Verify the primary key constraint name."""

    assert (
        SampleModel.__table__.primary_key.name
        == "pk_sample_models"
    )


def test_foreign_key_naming_convention():
    """Verify the foreign key constraint name."""

    table = RelatedSampleModel.__table__

    foreign_key_constraints = [
        constraint
        for constraint in table.constraints
        if constraint.__class__.__name__ == "ForeignKeyConstraint"
    ]

    assert len(foreign_key_constraints) == 1

    assert (
        foreign_key_constraints[0].name
        == "fk_related_sample_models_sample_id_sample_models"
    )


def test_unique_constraint_naming_convention():
    """Verify the unique constraint name."""

    table = RelatedSampleModel.__table__

    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert len(unique_constraints) == 1

    assert unique_constraints[0].name == "uq_related_sample_models_code"
