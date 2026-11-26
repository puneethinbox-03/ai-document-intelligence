
from types import SimpleNamespace
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from app.services.document_deletion_service import delete_owned_document


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def document_id():
    return uuid4()


@pytest.fixture
def mock_document(owner_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        storage_key="private/generated-document.pdf",
        status="deleting",
    )


@pytest.fixture
def mock_storage():
    return MagicMock()


def test_delete_owned_document_removes_files_and_database_record(
    mock_db,
    owner_id,
    document_id,
    mock_document,
    mock_storage,
    monkeypatch,
):
    import app.services.document_deletion_service as deletion_service

    mark_mock = MagicMock(return_value=mock_document)
    permanent_delete_mock = MagicMock(return_value=True)

    monkeypatch.setattr(
        deletion_service,
        "mark_owned_document_deleting",
        mark_mock,
    )
    monkeypatch.setattr(
        deletion_service,
        "permanently_delete_owned_document",
        permanent_delete_mock,
    )

    result = delete_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
        storage=mock_storage,
    )

    assert result is True

    mark_mock.assert_called_once_with(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert mock_storage.mock_calls == [
        call.delete_original(mock_document.storage_key),
        call.delete_sanitized(mock_document.storage_key),
    ]

    permanent_delete_mock.assert_called_once_with(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )


def test_delete_owned_document_returns_false_for_unowned_document(
    mock_db,
    owner_id,
    document_id,
    mock_storage,
    monkeypatch,
):
    import app.services.document_deletion_service as deletion_service

    mark_mock = MagicMock(return_value=None)
    permanent_delete_mock = MagicMock()

    monkeypatch.setattr(
        deletion_service,
        "mark_owned_document_deleting",
        mark_mock,
    )
    monkeypatch.setattr(
        deletion_service,
        "permanently_delete_owned_document",
        permanent_delete_mock,
    )

    result = delete_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
        storage=mock_storage,
    )

    assert result is False
    mock_storage.delete_original.assert_not_called()
    mock_storage.delete_sanitized.assert_not_called()
    permanent_delete_mock.assert_not_called()


def test_delete_owned_document_continues_when_files_are_missing(
    mock_db,
    owner_id,
    document_id,
    mock_document,
    mock_storage,
    monkeypatch,
):
    import app.services.document_deletion_service as deletion_service

    mock_storage.delete_original.return_value = False
    mock_storage.delete_sanitized.return_value = False

    monkeypatch.setattr(
        deletion_service,
        "mark_owned_document_deleting",
        MagicMock(return_value=mock_document),
    )
    permanent_delete_mock = MagicMock(return_value=True)
    monkeypatch.setattr(
        deletion_service,
        "permanently_delete_owned_document",
        permanent_delete_mock,
    )

    result = delete_owned_document(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
        storage=mock_storage,
    )

    assert result is True
    mock_storage.delete_original.assert_called_once_with(
        mock_document.storage_key
    )
    mock_storage.delete_sanitized.assert_called_once_with(
        mock_document.storage_key
    )
    permanent_delete_mock.assert_called_once()


def test_delete_owned_document_stops_if_original_file_deletion_fails(
    mock_db,
    owner_id,
    document_id,
    mock_document,
    mock_storage,
    monkeypatch,
):
    import app.services.document_deletion_service as deletion_service

    mock_storage.delete_original.side_effect = OSError("Storage failure")

    monkeypatch.setattr(
        deletion_service,
        "mark_owned_document_deleting",
        MagicMock(return_value=mock_document),
    )
    permanent_delete_mock = MagicMock()
    monkeypatch.setattr(
        deletion_service,
        "permanently_delete_owned_document",
        permanent_delete_mock,
    )

    with pytest.raises(OSError, match="Storage failure"):
        delete_owned_document(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            storage=mock_storage,
        )

    mock_storage.delete_sanitized.assert_not_called()
    permanent_delete_mock.assert_not_called()


def test_delete_owned_document_stops_if_sanitized_file_deletion_fails(
    mock_db,
    owner_id,
    document_id,
    mock_document,
    mock_storage,
    monkeypatch,
):
    import app.services.document_deletion_service as deletion_service

    mock_storage.delete_sanitized.side_effect = OSError("Storage failure")

    monkeypatch.setattr(
        deletion_service,
        "mark_owned_document_deleting",
        MagicMock(return_value=mock_document),
    )
    permanent_delete_mock = MagicMock()
    monkeypatch.setattr(
        deletion_service,
        "permanently_delete_owned_document",
        permanent_delete_mock,
    )

    with pytest.raises(OSError, match="Storage failure"):
        delete_owned_document(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            storage=mock_storage,
        )

    mock_storage.delete_original.assert_called_once_with(
        mock_document.storage_key
    )
    permanent_delete_mock.assert_not_called()


def test_delete_owned_document_preserves_retry_state_if_database_delete_fails(
    mock_db,
    owner_id,
    document_id,
    mock_document,
    mock_storage,
    monkeypatch,
):
    import app.services.document_deletion_service as deletion_service

    monkeypatch.setattr(
        deletion_service,
        "mark_owned_document_deleting",
        MagicMock(return_value=mock_document),
    )
    permanent_delete_mock = MagicMock(
        side_effect=RuntimeError("Database failure")
    )
    monkeypatch.setattr(
        deletion_service,
        "permanently_delete_owned_document",
        permanent_delete_mock,
    )

    with pytest.raises(RuntimeError, match="Database failure"):
        delete_owned_document(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            storage=mock_storage,
        )

    mock_storage.delete_original.assert_called_once_with(
        mock_document.storage_key
    )
    mock_storage.delete_sanitized.assert_called_once_with(
        mock_document.storage_key
    )
    permanent_delete_mock.assert_called_once()
