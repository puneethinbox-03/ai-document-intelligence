from sqlalchemy import Boolean, DateTime, String, UniqueConstraint

from app.models.base import Base
from app.models.user import User


def test_user_model_uses_shared_base_metadata():
    """Verify that User uses the application's shared metadata."""

    assert User.metadata is Base.metadata
    assert User.__tablename__ == "users"
    assert "users" in Base.metadata.tables


def test_user_has_expected_columns():
    """Verify that all expected user columns exist."""

    expected_columns = {
        "id",
        "email",
        "email_normalized",
        "password_hash",
        "display_name",
        "email_verified_at",
        "is_active",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        set(User.__table__.columns.keys())
    )


def test_user_email_and_password_columns():
    """Verify email and password hash column configuration."""

    table = User.__table__

    assert isinstance(table.c.email.type, String)
    assert table.c.email.type.length == 320
    assert table.c.email.nullable is False

    assert isinstance(table.c.email_normalized.type, String)
    assert table.c.email_normalized.type.length == 320
    assert table.c.email_normalized.nullable is False

    assert isinstance(table.c.password_hash.type, String)
    assert table.c.password_hash.type.length == 255
    assert table.c.password_hash.nullable is False


def test_user_normalized_email_has_unique_constraint():
    """Verify normalized email addresses are unique."""

    constraints = [
        constraint
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert len(constraints) == 1

    constraint = constraints[0]

    assert constraint.name == "uq_users_email_normalized"
    assert [column.name for column in constraint.columns] == [
        "email_normalized"
    ]


def test_user_optional_fields():
    """Verify that display name and email verification are optional."""

    table = User.__table__

    assert table.c.display_name.nullable is True
    assert isinstance(table.c.display_name.type, String)

    assert table.c.email_verified_at.nullable is True
    assert isinstance(table.c.email_verified_at.type, DateTime)
    assert table.c.email_verified_at.type.timezone is True


def test_user_active_default():
    """Verify that accounts are active by default."""

    column = User.__table__.c.is_active

    assert isinstance(column.type, Boolean)
    assert column.nullable is False
    assert column.default is not None
    assert column.server_default is not None
