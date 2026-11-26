from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.models.document import Document
from app.services.document_ownership_service import (
    create_owned_document,
    get_owned_document,
    list_owned_documents,
    mark_owned_document_deleting,
    permanently_delete_owned_document,
    update_owned_document_status,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def document_id():
    return uuid4()


def test_create_owned_document_assigns_authenticated_owner(
    mock_db,
    owner_id,
):
    document = create_owned_document(
        mock_db,
        owner_id=owner_id,
        original_filename="report.pdf",
        storage_key=f"{owner_id}/documents/report-123.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="a" * 64,
    )

    assert isinstance(document, Document)
    assert document.user_id == owner_id
    assert document.original_filename == "report.pdf"
    assert document.storage_key == (
        f"{owner_id}/documents/report-123.pdf"
    )
    assert document.content_type == "application/pdf"
    assert document.file_size_bytes == 1024
    assert document.sha256_hash == "a" * 64
    assert document.status == "uploaded"

    mock_db.add.assert_called_once_with(document)
    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_create_owned_document_rolls_back_on_database_failure(
    mock_db,
    owner_id,
):
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        create_owned_document(
            mock_db,
            owner_id=owner_id,
            original_filename="report.pdf",
            storage_key="private/report.pdf",
            content_type="application/pdf",
            file_size_bytes=1024,
        )

    mock_db.rollback.assert_called_once()


def test_get_owned_document_filters_by_document_and_owner(
    mock_db,
    owner_id,
    document_id,
):
    expected_document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )
    mock_db.scalar.return_value = expected_document

    result = get_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is expected_document

    statement = mock_db.scalar.call_args.args[0]
    compiled = statement.compile()

    assert "documents.id" in str(compiled)
    assert "documents.user_id" in str(compiled)
    assert document_id in compiled.params.values()
    assert owner_id in compiled.params.values()


def test_get_owned_document_returns_none_when_not_found(
    mock_db,
    owner_id,
    document_id,
):
    mock_db.scalar.return_value = None

    result = get_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is None


def test_list_owned_documents_filters_by_owner(
    mock_db,
    owner_id,
):
    expected_documents = [
        MagicMock(spec=Document),
        MagicMock(spec=Document),
    ]
    mock_db.scalars.return_value.all.return_value = expected_documents

    result = list_owned_documents(
        mock_db,
        owner_id=owner_id,
    )

    assert result == expected_documents

    statement = mock_db.scalars.call_args.args[0]
    compiled = statement.compile()

    assert "documents.user_id" in str(compiled)
    assert owner_id in compiled.params.values()


def test_list_owned_documents_supports_pagination(
    mock_db,
    owner_id,
):
    mock_db.scalars.return_value.all.return_value = []

    list_owned_documents(
        mock_db,
        owner_id=owner_id,
        skip=10,
        limit=20,
    )

    statement = mock_db.scalars.call_args.args[0]
    compiled = statement.compile()

    assert compiled.params["param_1"] == 20
    assert compiled.params["param_2"] == 10


@pytest.mark.parametrize(
    ("skip", "limit"),
    [
        (-1, 10),
        (0, 0),
        (0, 101),
    ],
)
def test_list_owned_documents_rejects_invalid_pagination(
    mock_db,
    owner_id,
    skip,
    limit,
):
    with pytest.raises(ValueError):
        list_owned_documents(
            mock_db,
            owner_id=owner_id,
            skip=skip,
            limit=limit,
        )

    mock_db.scalars.assert_not_called()


def test_update_owned_document_status_updates_only_owned_document(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )
    mock_db.scalar.return_value = document

    result = update_owned_document_status(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
        status="indexed",
    )

    assert result is document
    assert document.status == "indexed"
    assert document.error_code is None
    assert document.error_message is None
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_update_owned_document_status_returns_none_for_unowned_document(
    mock_db,
    owner_id,
    document_id,
):
    mock_db.scalar.return_value = None

    result = update_owned_document_status(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
        status="indexed",
    )

    assert result is None
    mock_db.commit.assert_not_called()


def test_update_owned_document_status_rejects_invalid_status(
    mock_db,
    owner_id,
    document_id,
):
    with pytest.raises(ValueError, match="Invalid document status"):
        update_owned_document_status(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            status="unauthorized-status",
        )

    mock_db.scalar.assert_not_called()
    mock_db.commit.assert_not_called()


def test_update_owned_document_status_rolls_back_on_commit_failure(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )
    mock_db.scalar.return_value = document
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        update_owned_document_status(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            status="indexed",
        )

    mock_db.rollback.assert_called_once()



# ============================================================
# Document deletion ownership tests
# ============================================================

def test_mark_owned_document_deleting_updates_status(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )
    mock_db.scalar.return_value = document

    result = mark_owned_document_deleting(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is document
    assert document.status == "deleting"
    assert document.error_code is None
    assert document.error_message is None
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_mark_owned_document_deleting_returns_none_for_unowned_document(
    mock_db,
    owner_id,
    document_id,
):
    mock_db.scalar.return_value = None

    result = mark_owned_document_deleting(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is None
    mock_db.commit.assert_not_called()


def test_mark_owned_document_deleting_does_not_commit_if_already_deleting(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="deleting",
    )
    mock_db.scalar.return_value = document

    result = mark_owned_document_deleting(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is document
    assert document.status == "deleting"
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_not_called()


def test_mark_owned_document_deleting_rolls_back_on_commit_failure(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
    )
    mock_db.scalar.return_value = document
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        mark_owned_document_deleting(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
        )

    mock_db.rollback.assert_called_once()


def test_permanently_delete_owned_document_deletes_deleting_record(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="deleting",
    )
    mock_db.scalar.return_value = document

    result = permanently_delete_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is True
    mock_db.delete.assert_called_once_with(document)
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_permanently_delete_owned_document_returns_false_for_unowned_document(
    mock_db,
    owner_id,
    document_id,
):
    mock_db.scalar.return_value = None

    result = permanently_delete_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is False
    mock_db.delete.assert_not_called()
    mock_db.commit.assert_not_called()


def test_permanently_delete_owned_document_rejects_other_status(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="uploaded",
    )
    mock_db.scalar.return_value = document

    with pytest.raises(
        ValueError,
        match="Document must be marked as deleting",
    ):
        permanently_delete_owned_document(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
        )

    mock_db.delete.assert_not_called()
    mock_db.commit.assert_not_called()


def test_permanently_delete_owned_document_rolls_back_on_commit_failure(
    mock_db,
    owner_id,
    document_id,
):
    document = Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="deleting",
    )
    mock_db.scalar.return_value = document
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        permanently_delete_owned_document(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
        )

    mock_db.delete.assert_called_once_with(document)
    mock_db.rollback.assert_called_once()
