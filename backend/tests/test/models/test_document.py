from sqlalchemy import BigInteger, String

from app.models.base import Base
from app.models.document import Document


def test_document_uses_shared_metadata():
    """Verify the document model uses shared metadata."""

    assert Document.metadata is Base.metadata
    assert Document.__tablename__ == "documents"
    assert "documents" in Base.metadata.tables


def test_document_has_expected_columns():
    """Verify all expected document columns exist."""

    expected_columns = {
        "id",
        "user_id",
        "original_filename",
        "storage_key",
        "content_type",
        "file_size_bytes",
        "sha256_hash",
        "status",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
    }

    actual_columns = set(Document.__table__.columns.keys())

    assert expected_columns.issubset(actual_columns)


def test_document_user_foreign_key():
    """Verify each document references its owning user."""

    column = Document.__table__.c.user_id

    assert column.nullable is False
    assert len(column.foreign_keys) == 1

    foreign_key = next(iter(column.foreign_keys))

    assert foreign_key.target_fullname == "users.id"


def test_document_file_metadata_configuration():
    """Verify filename, storage key, content type and file size."""

    table = Document.__table__

    assert isinstance(table.c.original_filename.type, String)
    assert table.c.original_filename.type.length == 255
    assert table.c.original_filename.nullable is False

    assert isinstance(table.c.storage_key.type, String)
    assert table.c.storage_key.type.length == 512
    assert table.c.storage_key.nullable is False

    assert isinstance(table.c.content_type.type, String)
    assert table.c.content_type.type.length == 127
    assert table.c.content_type.nullable is False

    assert isinstance(table.c.file_size_bytes.type, BigInteger)
    assert table.c.file_size_bytes.nullable is False


def test_document_optional_metadata():
    """Verify checksum and processing error fields are optional."""

    table = Document.__table__

    assert table.c.sha256_hash.nullable is True
    assert table.c.sha256_hash.type.length == 64

    assert table.c.error_code.nullable is True
    assert table.c.error_code.type.length == 100

    assert table.c.error_message.nullable is True
    assert table.c.error_message.type.length == 500


def test_document_status_default():
    """Verify new documents start in the uploaded state."""

    column = Document.__table__.c.status

    assert isinstance(column.type, String)
    assert column.type.length == 20
    assert column.nullable is False
    assert column.default.arg == "uploaded"
    assert column.server_default is not None


def test_document_timestamp_configuration():
    """Verify inherited timestamp columns are configured."""

    table = Document.__table__

    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False

    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True
