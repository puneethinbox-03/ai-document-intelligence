from app.models.base import Base
from app.models.chat import Chat, ChatDocument


def test_chat_models_use_shared_metadata():
    """Verify both chat models use shared application metadata."""

    assert Chat.metadata is Base.metadata
    assert ChatDocument.metadata is Base.metadata

    assert Chat.__tablename__ == "chats"
    assert ChatDocument.__tablename__ == "chat_documents"


def test_chat_has_expected_columns():
    """Verify chat columns exist."""

    expected_columns = {
        "id",
        "user_id",
        "title",
        "created_at",
        "updated_at",
    }

    actual_columns = set(Chat.__table__.columns.keys())

    assert expected_columns.issubset(actual_columns)


def test_chat_user_foreign_key():
    """Verify each chat references its owner."""

    column = Chat.__table__.c.user_id

    assert column.nullable is False
    assert len(column.foreign_keys) == 1

    foreign_key = next(iter(column.foreign_keys))

    assert foreign_key.target_fullname == "users.id"


def test_chat_title_configuration():
    """Verify chat title configuration and default."""

    column = Chat.__table__.c.title

    assert column.type.length == 255
    assert column.nullable is False
    assert column.default.arg == "New Chat"
    assert column.server_default is not None


def test_chat_document_has_expected_columns():
    """Verify chat-document association columns exist."""

    expected_columns = {
        "id",
        "chat_id",
        "document_id",
        "created_at",
        "updated_at",
    }

    actual_columns = set(ChatDocument.__table__.columns.keys())

    assert expected_columns.issubset(actual_columns)


def test_chat_document_foreign_keys():
    """Verify the association references chats and documents."""

    table = ChatDocument.__table__

    expected_targets = {
        "chat_id": "chats.id",
        "document_id": "documents.id",
    }

    for column_name, expected_target in expected_targets.items():
        column = table.c[column_name]

        assert column.nullable is False
        assert len(column.foreign_keys) == 1

        foreign_key = next(iter(column.foreign_keys))

        assert foreign_key.target_fullname == expected_target


def test_chat_models_have_inherited_timestamps():
    """Verify both models inherit timestamp columns."""

    for model in (Chat, ChatDocument):
        table = model.__table__

        assert table.c.created_at.nullable is False
        assert table.c.updated_at.nullable is False

        assert table.c.created_at.type.timezone is True
        assert table.c.updated_at.type.timezone is True
