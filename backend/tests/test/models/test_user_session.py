from sqlalchemy import DateTime, ForeignKey, String

from app.models.base import Base
from app.models.user_session import UserSession


def test_user_session_uses_shared_metadata():
    """Verify the session model uses shared application metadata."""

    assert UserSession.metadata is Base.metadata
    assert UserSession.__tablename__ == "user_sessions"
    assert "user_sessions" in Base.metadata.tables


def test_user_session_has_expected_columns():
    """Verify all expected session columns exist."""

    expected_columns = {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        set(UserSession.__table__.columns.keys())
    )


def test_user_session_user_foreign_key():
    """Verify that each session references a user."""

    column = UserSession.__table__.c.user_id

    assert column.nullable is False
    assert len(column.foreign_keys) == 1

    foreign_key = next(iter(column.foreign_keys))

    assert foreign_key.target_fullname == "users.id"


def test_user_session_token_hash_configuration():
    """Verify that only a bounded token hash is stored."""

    column = UserSession.__table__.c.token_hash

    assert isinstance(column.type, String)
    assert column.type.length == 64
    assert column.nullable is False


def test_user_session_timestamp_configuration():
    """Verify session timestamps are timezone-aware."""

    table = UserSession.__table__

    assert isinstance(table.c.expires_at.type, DateTime)
    assert table.c.expires_at.type.timezone is True
    assert table.c.expires_at.nullable is False

    assert table.c.revoked_at.nullable is True
    assert table.c.revoked_at.type.timezone is True

    assert table.c.last_used_at.nullable is True
    assert table.c.last_used_at.type.timezone is True
