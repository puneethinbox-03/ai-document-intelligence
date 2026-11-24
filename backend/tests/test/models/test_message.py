from sqlalchemy import JSON, String, Text

from app.models.base import Base
from app.models.message import Message


def test_message_uses_shared_metadata():
    """Verify the message model uses shared application metadata."""

    assert Message.metadata is Base.metadata
    assert Message.__tablename__ == "messages"
    assert "messages" in Base.metadata.tables


def test_message_has_expected_columns():
    """Verify all expected message columns exist."""

    expected_columns = {
        "id",
        "chat_id",
        "role",
        "content",
        "source_metadata",
        "created_at",
        "updated_at",
    }

    actual_columns = set(Message.__table__.columns.keys())

    assert expected_columns.issubset(actual_columns)


def test_message_chat_foreign_key():
    """Verify each message references its chat."""

    column = Message.__table__.c.chat_id

    assert column.nullable is False
    assert len(column.foreign_keys) == 1

    foreign_key = next(iter(column.foreign_keys))

    assert foreign_key.target_fullname == "chats.id"


def test_message_role_configuration():
    """Verify message role is a required bounded string."""

    column = Message.__table__.c.role

    assert isinstance(column.type, String)
    assert column.type.length == 20
    assert column.nullable is False


def test_message_content_configuration():
    """Verify message content uses an unrestricted text column."""

    column = Message.__table__.c.content

    assert isinstance(column.type, Text)
    assert column.nullable is False


def test_message_source_metadata_configuration():
    """Verify source metadata is optional JSON."""

    column = Message.__table__.c.source_metadata

    assert isinstance(column.type, JSON)
    assert column.nullable is True


def test_message_timestamp_configuration():
    """Verify inherited timestamps are timezone-aware."""

    table = Message.__table__

    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False

    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True


def test_message_role_check_constraint():
    from sqlalchemy import CheckConstraint

    constraints = [
        constraint
        for constraint in Message.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    assert any(
        constraint.name == "ck_messages_role_valid"
        for constraint in constraints
    )


def test_message_chat_id_created_at_index():
    indexes = {
        index.name: index
        for index in Message.__table__.indexes
    }

    index = indexes["ix_messages_chat_id_created_at"]

    assert [column.name for column in index.columns] == [
        "chat_id",
        "created_at",
    ]


def test_message_chat_foreign_key_cascades_on_delete():
    foreign_keys = list(Message.__table__.c.chat_id.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].ondelete == "CASCADE"
