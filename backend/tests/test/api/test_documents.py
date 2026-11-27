
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import documents as documents_api
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models import User
from app.services.document_storage_service import StoredDocument


@pytest.fixture
def client():
    """Create a test client without connecting to PostgreSQL."""

    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def create_verified_user():
    """Create an in-memory authenticated user."""

    now = datetime.now(timezone.utc)

    return User(
        id=uuid4(),
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="test-password-hash",
        display_name="Test Person",
        email_verified_at=now,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def authenticate(client, user=None):
    """Override authentication and return the test user."""

    user = user or create_verified_user()

    app.dependency_overrides[get_current_user] = lambda: user

    return user


def get_csrf_headers(client):
    """Obtain a valid CSRF token and request headers."""

    response = client.get("/api/auth/csrf")

    assert response.status_code == 200

    token = response.json()["csrf_token"]

    return {
        "Origin": settings.frontend_url,
        "X-CSRF-Token": token,
    }


def make_stored_document():
    """Create a representative stored-document result."""

    return StoredDocument(
        storage_key="generated-document-key.pdf",
        original_filename="report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="a" * 64,
    )


def make_database_document(user_id):
    """Create a document-like database result."""

    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        original_filename="report.pdf",
        storage_key="generated-document-key.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="uploaded",
    )


# ---------------------------------------------------------------------------
# Document upload tests
# ---------------------------------------------------------------------------

def test_upload_requires_authentication(client):
    headers = get_csrf_headers(client)

    response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "report.pdf",
                b"sample document",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_upload_requires_csrf(client):
    authenticate(client)

    response = client.post(
        "/api/documents/upload",
        headers={
            "Origin": settings.frontend_url,
        },
        files={
            "file": (
                "report.pdf",
                b"sample document",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_upload_creates_document_and_processing_job(
    client,
    monkeypatch,
):
    user = authenticate(client)
    stored = make_stored_document()
    database_document = make_database_document(user.id)

    processing_job_id = uuid4()
    dispatch_calls = []

    database_document.status = "queued"

    async def mock_save_original(upload):
        return stored

    def mock_create_document_and_job(db, **kwargs):
        assert kwargs["owner_id"] == user.id
        assert kwargs["storage_key"] == stored.storage_key
        assert kwargs["original_filename"] == stored.original_filename
        assert kwargs["sha256_hash"] == stored.sha256_hash

        processing_job = SimpleNamespace(
            id=processing_job_id,
        )

        return database_document, processing_job

    def mock_dispatch(**kwargs):
        dispatch_calls.append(kwargs)
        return {
            "claimed": 1,
            "dispatched": 1,
            "failed": 0,
            "stale": 0,
        }

    monkeypatch.setattr(
        documents_api.document_storage,
        "save_original",
        mock_save_original,
    )
    monkeypatch.setattr(
        documents_api,
        "create_owned_document_with_processing_job",
        mock_create_document_and_job,
    )
    monkeypatch.setattr(
        documents_api,
        "dispatch_pending_document_jobs",
        mock_dispatch,
    )

    response = client.post(
        "/api/documents/upload",
        headers=get_csrf_headers(client),
        files={
            "file": (
                "report.pdf",
                b"sample document",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["document_id"] == str(database_document.id)
    assert data["filename"] == "report.pdf"
    assert data["file_type"] == "pdf"
    assert data["file_size"] == 1024
    assert data["status"] == "queued"

    assert dispatch_calls == [{"batch_size": 10}]


def test_upload_keeps_document_when_redis_enqueue_fails(
    client,
    monkeypatch,
):
    user = authenticate(client)
    stored = make_stored_document()
    database_document = make_database_document(user.id)

    database_document.status = "queued"

    async def mock_save_original(upload):
        return stored

    def mock_create_document_and_job(db, **kwargs):
        assert kwargs["owner_id"] == user.id

        return (
            database_document,
            SimpleNamespace(id=uuid4()),
        )

    def fail_dispatch(**kwargs):
        raise RuntimeError("Redis is unavailable")

    deleted_keys = []

    monkeypatch.setattr(
        documents_api.document_storage,
        "save_original",
        mock_save_original,
    )
    monkeypatch.setattr(
        documents_api,
        "create_owned_document_with_processing_job",
        mock_create_document_and_job,
    )
    monkeypatch.setattr(
        documents_api,
        "dispatch_pending_document_jobs",
        fail_dispatch,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "delete_original",
        lambda key: deleted_keys.append(key),
    )

    response = client.post(
        "/api/documents/upload",
        headers=get_csrf_headers(client),
        files={
            "file": (
                "report.pdf",
                b"sample document",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "queued"

    # Redis failure must not delete the original document.
    assert deleted_keys == []


def test_upload_rejects_storage_validation_error(
    client,
    monkeypatch,
):
    authenticate(client)

    async def reject_upload(upload):
        raise ValueError("Unsupported document file type.")

    monkeypatch.setattr(
        documents_api.document_storage,
        "save_original",
        reject_upload,
    )

    response = client.post(
        "/api/documents/upload",
        headers=get_csrf_headers(client),
        files={
            "file": (
                "report.exe",
                b"invalid content",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert response.json()["error"]["message"] == (
        "Unsupported document file type."
    )


def test_upload_cleans_up_original_when_database_creation_fails(
    client,
    monkeypatch,
):
    authenticate(client)
    stored = make_stored_document()
    deleted_keys = []

    async def mock_save_original(upload):
        return stored

    def fail_database_creation(db, **kwargs):
        raise RuntimeError("sensitive internal database details")

    def mock_delete_original(storage_key):
        deleted_keys.append(storage_key)
        return True

    monkeypatch.setattr(
        documents_api.document_storage,
        "save_original",
        mock_save_original,
    )
    monkeypatch.setattr(
        documents_api,
        "create_owned_document_with_processing_job",
        fail_database_creation,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "delete_original",
        mock_delete_original,
    )

    response = client.post(
        "/api/documents/upload",
        headers=get_csrf_headers(client),
        files={
            "file": (
                "report.pdf",
                b"sample document",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert response.json()["error"]["message"] == (
        "An internal server error occurred"
    )
    assert "sensitive internal database details" not in response.text
    assert deleted_keys == [stored.storage_key]


# ---------------------------------------------------------------------------
# Document listing tests
# ---------------------------------------------------------------------------

def test_list_documents_returns_only_service_results_for_owner(
    client,
    monkeypatch,
):
    user = authenticate(client)
    database_document = make_database_document(user.id)
    requested_owners = []

    def mock_list_owned_documents(db, *, owner_id, skip=0, limit=50):
        requested_owners.append(owner_id)
        return [database_document]

    monkeypatch.setattr(
        documents_api,
        "list_owned_documents",
        mock_list_owned_documents,
    )

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["document_id"] == str(database_document.id)
    assert requested_owners == [user.id]


def test_list_documents_requires_authentication(client):
    response = client.get("/api/documents")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_list_documents_passes_pagination_to_service(
    client,
    monkeypatch,
):
    user = authenticate(client)
    requested_values = {}

    def mock_list_owned_documents(db, **kwargs):
        requested_values.update(kwargs)
        return []

    monkeypatch.setattr(
        documents_api,
        "list_owned_documents",
        mock_list_owned_documents,
    )

    response = client.get(
        "/api/documents?skip=20&limit=10"
    )

    assert response.status_code == 200
    assert response.json() == []
    assert requested_values["owner_id"] == user.id
    assert requested_values["skip"] == 20
    assert requested_values["limit"] == 10


def test_list_documents_uses_default_pagination(
    client,
    monkeypatch,
):
    user = authenticate(client)
    requested_values = {}

    def mock_list_owned_documents(db, **kwargs):
        requested_values.update(kwargs)
        return []

    monkeypatch.setattr(
        documents_api,
        "list_owned_documents",
        mock_list_owned_documents,
    )

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert requested_values["owner_id"] == user.id
    assert requested_values["skip"] == 0
    assert requested_values["limit"] == 50


@pytest.mark.parametrize(
    "query",
    [
        "?skip=-1",
        "?limit=0",
        "?limit=101",
    ],
)
def test_list_documents_rejects_invalid_pagination(
    client,
    monkeypatch,
    query,
):
    authenticate(client)

    service_called = False

    def mock_list_owned_documents(db, **kwargs):
        nonlocal service_called
        service_called = True
        return []

    monkeypatch.setattr(
        documents_api,
        "list_owned_documents",
        mock_list_owned_documents,
    )

    response = client.get(
        f"/api/documents{query}"
    )

    assert response.status_code == 422
    assert service_called is False


# ---------------------------------------------------------------------------
# Get document tests
# ---------------------------------------------------------------------------

def test_get_document_returns_404_for_document_not_owned(
    client,
    monkeypatch,
):
    authenticate(client)

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: None,
    )

    response = client.get(
        f"/api/documents/{uuid4()}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"] == "Document not found"


def test_get_document_requires_authentication(client):
    response = client.get(
        f"/api/documents/{uuid4()}"
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_document_returns_owned_document(
    client,
    monkeypatch,
):
    user = authenticate(client)
    database_document = make_database_document(user.id)
    requested_values = {}

    def mock_get_owned_document(db, **kwargs):
        requested_values.update(kwargs)
        return database_document

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        mock_get_owned_document,
    )

    response = client.get(
        f"/api/documents/{database_document.id}"
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == str(database_document.id)
    assert response.json()["filename"] == "report.pdf"
    assert requested_values["owner_id"] == user.id
    assert requested_values["document_id"] == database_document.id


# ---------------------------------------------------------------------------
# Document text extraction tests
# ---------------------------------------------------------------------------

def test_extract_document_text_requires_authentication(client):
    response = client.get(
        f"/api/documents/{uuid4()}/text"
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_extract_document_text_rejects_non_owned_document(
    client,
    monkeypatch,
):
    authenticate(client)

    extraction_called = False

    def mock_get_owned_document(db, **kwargs):
        return None

    def mock_extract_document_text(path):
        nonlocal extraction_called
        extraction_called = True
        return "private document text"

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        mock_get_owned_document,
    )
    monkeypatch.setattr(
        documents_api,
        "extract_document_text",
        mock_extract_document_text,
    )

    response = client.get(
        f"/api/documents/{uuid4()}/text"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert extraction_called is False


def test_extract_document_text_returns_owned_document_text(
    client,
    monkeypatch,
    tmp_path,
):
    user = authenticate(client)
    database_document = make_database_document(user.id)

    document_path = tmp_path / "report.pdf"
    document_path.write_bytes(b"test PDF placeholder")

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: database_document,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "get_original_path",
        lambda storage_key: document_path,
    )
    monkeypatch.setattr(
        documents_api,
        "extract_document_text",
        lambda path: "Example extracted document text.",
    )

    response = client.get(
        f"/api/documents/{database_document.id}/text"
    )

    assert response.status_code == 200
    assert response.json()["document_id"] == str(database_document.id)
    assert response.json()["text"] == "Example extracted document text."


# ---------------------------------------------------------------------------
# Secure document download tests
# ---------------------------------------------------------------------------

def test_download_document_requires_authentication(client):
    response = client.get(
        f"/api/documents/{uuid4()}/download"
    )

    assert response.status_code == 401


def test_owner_can_download_original_document(
    client,
    monkeypatch,
    tmp_path,
):
    user = authenticate(client)
    document = make_database_document(user.id)

    document_path = tmp_path / "report.pdf"
    expected_content = b"%PDF-1.7 example document content"
    document_path.write_bytes(expected_content)

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "get_original_path",
        lambda storage_key: document_path,
    )

    response = client.get(
        f"/api/documents/{document.id}/download"
    )

    assert response.status_code == 200
    assert response.content == expected_content
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="report.pdf"' in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"

    assert str(tmp_path) not in str(response.headers)
    assert str(tmp_path).encode() not in response.content


def test_non_owner_cannot_download_document(
    client,
    monkeypatch,
):
    authenticate(client)

    storage_path_called = False

    def reject_document(db, **kwargs):
        return None

    def track_storage_access(storage_key):
        nonlocal storage_path_called
        storage_path_called = True
        raise AssertionError(
            "Storage must not be accessed for an unowned document."
        )

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        reject_document,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "get_original_path",
        track_storage_access,
    )

    response = client.get(
        f"/api/documents/{uuid4()}/download"
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document not found"
    assert storage_path_called is False


def test_download_returns_404_when_original_file_is_missing(
    client,
    monkeypatch,
    tmp_path,
):
    user = authenticate(client)
    document = make_database_document(user.id)

    missing_path = tmp_path / "missing.pdf"

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "get_original_path",
        lambda storage_key: missing_path,
    )

    response = client.get(
        f"/api/documents/{document.id}/download"
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document file not found"


def test_download_returns_safe_error_for_invalid_storage_key(
    client,
    monkeypatch,
):
    user = authenticate(client)
    document = make_database_document(user.id)

    def reject_storage_key(storage_key):
        raise ValueError("Internal storage path information")

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )
    monkeypatch.setattr(
        documents_api.document_storage,
        "get_original_path",
        reject_storage_key,
    )

    response = client.get(
        f"/api/documents/{document.id}/download"
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document file not found"
    assert "Internal storage path information" not in response.text


# ---------------------------------------------------------------------------
# Secure document deletion API tests
# ---------------------------------------------------------------------------

def test_delete_document_requires_authentication(client):
    headers = get_csrf_headers(client)

    response = client.delete(
        f"/api/documents/{uuid4()}",
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_delete_document_requires_csrf(
    client,
    monkeypatch,
):
    authenticate(client)

    deletion_called = False

    def track_deletion(db, **kwargs):
        nonlocal deletion_called
        deletion_called = True
        return True

    monkeypatch.setattr(
        documents_api,
        "delete_owned_document",
        track_deletion,
    )

    response = client.delete(
        f"/api/documents/{uuid4()}",
        headers={
            "Origin": settings.frontend_url,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert deletion_called is False


def test_non_owner_cannot_delete_document(
    client,
    monkeypatch,
):
    user = authenticate(client)
    requested_values = {}

    def reject_unowned_document(db, **kwargs):
        requested_values.update(kwargs)
        return False

    monkeypatch.setattr(
        documents_api,
        "delete_owned_document",
        reject_unowned_document,
    )

    response = client.delete(
        f"/api/documents/{uuid4()}",
        headers=get_csrf_headers(client),
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document not found"
    assert requested_values["owner_id"] == user.id
    assert "document_id" in requested_values


def test_owner_can_delete_document(
    client,
    monkeypatch,
):
    user = authenticate(client)
    document_id = uuid4()
    requested_values = {}

    def mock_delete_owned_document(db, **kwargs):
        requested_values.update(kwargs)
        return True

    monkeypatch.setattr(
        documents_api,
        "delete_owned_document",
        mock_delete_owned_document,
    )

    response = client.delete(
        f"/api/documents/{document_id}",
        headers=get_csrf_headers(client),
    )

    assert response.status_code == 204
    assert response.content == b""
    assert requested_values["document_id"] == document_id
    assert requested_values["owner_id"] == user.id


def test_delete_document_returns_safe_error_on_deletion_failure(
    client,
    monkeypatch,
):
    authenticate(client)

    def fail_deletion(db, **kwargs):
        raise RuntimeError("Sensitive internal storage information")

    monkeypatch.setattr(
        documents_api,
        "delete_owned_document",
        fail_deletion,
    )

    response = client.delete(
        f"/api/documents/{uuid4()}",
        headers=get_csrf_headers(client),
    )

    assert response.status_code == 500
    assert response.json()["error"]["message"] == (
        "An internal server error occurred"
    )
    assert "Sensitive internal storage information" not in response.text


# ---------------------------------------------------------------------------
# Document processing job API tests
# ---------------------------------------------------------------------------

def make_database_processing_job(document_id, **overrides):
    """Create a representative processing-job database result."""

    now = datetime.now(timezone.utc)

    values = {
        "id": uuid4(),
        "document_id": document_id,
        "status": "queued",
        "attempts": 0,
        "max_attempts": 3,
        "available_at": now,
        "started_at": None,
        "completed_at": None,
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }

    values.update(overrides)

    return SimpleNamespace(**values)


# ---------------------------------------------------------------------------
# List processing jobs
# ---------------------------------------------------------------------------

def test_list_processing_jobs_requires_authentication(client):
    response = client.get(
        f"/api/documents/{uuid4()}/jobs"
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_list_processing_jobs_rejects_unowned_document(
    client,
    monkeypatch,
):
    authenticate(client)

    list_called = False

    def reject_document(db, **kwargs):
        return None

    def track_list_jobs(db, **kwargs):
        nonlocal list_called
        list_called = True
        return []

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        reject_document,
    )
    monkeypatch.setattr(
        documents_api,
        "list_owned_processing_jobs",
        track_list_jobs,
    )

    response = client.get(
        f"/api/documents/{uuid4()}/jobs"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"] == "Document not found"

    # Jobs must never be queried for an unowned document.
    assert list_called is False


def test_list_processing_jobs_returns_owned_document_jobs(
    client,
    monkeypatch,
):
    user = authenticate(client)

    document = make_database_document(user.id)

    job = make_database_processing_job(document.id)

    requested_values = {}

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )

    def mock_list_jobs(db, **kwargs):
        requested_values.update(kwargs)
        return [job]

    monkeypatch.setattr(
        documents_api,
        "list_owned_processing_jobs",
        mock_list_jobs,
    )

    response = client.get(
        f"/api/documents/{document.id}/jobs"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["job_id"] == str(job.id)
    assert data[0]["document_id"] == str(document.id)
    assert data[0]["status"] == "queued"
    assert data[0]["attempts"] == 0
    assert data[0]["max_attempts"] == 3

    assert requested_values["document_id"] == document.id
    assert requested_values["owner_id"] == user.id
    assert requested_values["skip"] == 0
    assert requested_values["limit"] == 50


def test_list_processing_jobs_passes_pagination(
    client,
    monkeypatch,
):
    user = authenticate(client)

    document = make_database_document(user.id)

    requested_values = {}

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )

    def mock_list_jobs(db, **kwargs):
        requested_values.update(kwargs)
        return []

    monkeypatch.setattr(
        documents_api,
        "list_owned_processing_jobs",
        mock_list_jobs,
    )

    response = client.get(
        f"/api/documents/{document.id}/jobs?skip=10&limit=20"
    )

    assert response.status_code == 200
    assert response.json() == []

    assert requested_values["owner_id"] == user.id
    assert requested_values["document_id"] == document.id
    assert requested_values["skip"] == 10
    assert requested_values["limit"] == 20


@pytest.mark.parametrize(
    "query",
    [
        "?skip=-1",
        "?limit=0",
        "?limit=101",
    ],
)
def test_list_processing_jobs_rejects_invalid_pagination(
    client,
    monkeypatch,
    query,
):
    authenticate(client)

    ownership_check_called = False

    def track_ownership(db, **kwargs):
        nonlocal ownership_check_called
        ownership_check_called = True
        return make_database_document(kwargs["owner_id"])

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        track_ownership,
    )

    response = client.get(
        f"/api/documents/{uuid4()}/jobs{query}"
    )

    assert response.status_code == 422

    # FastAPI must reject invalid parameters before endpoint execution.
    assert ownership_check_called is False


# ---------------------------------------------------------------------------
# Get individual processing job
# ---------------------------------------------------------------------------

def test_get_processing_job_requires_authentication(client):
    response = client.get(
        f"/api/documents/{uuid4()}/jobs/{uuid4()}"
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_processing_job_rejects_unowned_document(
    client,
    monkeypatch,
):
    authenticate(client)

    job_lookup_called = False

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: None,
    )

    def track_job_lookup(db, **kwargs):
        nonlocal job_lookup_called
        job_lookup_called = True
        return None

    monkeypatch.setattr(
        documents_api,
        "get_owned_processing_job",
        track_job_lookup,
    )

    response = client.get(
        f"/api/documents/{uuid4()}/jobs/{uuid4()}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document not found"

    assert job_lookup_called is False


def test_get_processing_job_returns_owned_job(
    client,
    monkeypatch,
):
    user = authenticate(client)

    document = make_database_document(user.id)

    job = make_database_processing_job(document.id)

    requested_values = {}

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )

    def mock_get_job(db, **kwargs):
        requested_values.update(kwargs)
        return job

    monkeypatch.setattr(
        documents_api,
        "get_owned_processing_job",
        mock_get_job,
    )

    response = client.get(
        f"/api/documents/{document.id}/jobs/{job.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == str(job.id)
    assert data["document_id"] == str(document.id)
    assert data["status"] == "queued"
    assert data["attempts"] == 0
    assert data["max_attempts"] == 3
    assert data["error_code"] is None
    assert data["error_message"] is None

    assert requested_values["processing_job_id"] == job.id
    assert requested_values["owner_id"] == user.id


def test_get_processing_job_rejects_job_from_another_document(
    client,
    monkeypatch,
):
    user = authenticate(client)

    requested_document = make_database_document(user.id)

    another_document_id = uuid4()

    job = make_database_processing_job(
        another_document_id
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: requested_document,
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_processing_job",
        lambda db, **kwargs: job,
    )

    response = client.get(
        f"/api/documents/{requested_document.id}/jobs/{job.id}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["message"] == "Document not found"


def test_get_processing_job_returns_404_for_unowned_job(
    client,
    monkeypatch,
):
    user = authenticate(client)

    document = make_database_document(user.id)

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_processing_job",
        lambda db, **kwargs: None,
    )

    response = client.get(
        f"/api/documents/{document.id}/jobs/{uuid4()}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document not found"


# ---------------------------------------------------------------------------
# Safe processing-job error responses
# ---------------------------------------------------------------------------

def test_processing_job_returns_safe_error_message(
    client,
    monkeypatch,
):
    user = authenticate(client)

    document = make_database_document(user.id)

    job = make_database_processing_job(
        document.id,
        status="failed",
        attempts=3,
        error_code="PROCESSING_FAILED",
        error_message="Internal database connection password",
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_processing_job",
        lambda db, **kwargs: job,
    )

    response = client.get(
        f"/api/documents/{document.id}/jobs/{job.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["error_code"] == "PROCESSING_FAILED"
    assert data["error_message"] == "Document processing failed"

    assert "Internal database connection password" not in response.text
    assert "password" not in response.text


def test_processing_job_hides_unknown_error_details(
    client,
    monkeypatch,
):
    user = authenticate(client)

    document = make_database_document(user.id)

    job = make_database_processing_job(
        document.id,
        status="failed",
        error_code="INTERNAL_DATABASE_FAILURE",
        error_message="Sensitive internal system details",
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_document",
        lambda db, **kwargs: document,
    )

    monkeypatch.setattr(
        documents_api,
        "get_owned_processing_job",
        lambda db, **kwargs: job,
    )

    response = client.get(
        f"/api/documents/{document.id}/jobs/{job.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["error_code"] is None
    assert data["error_message"] is None

    assert "INTERNAL_DATABASE_FAILURE" not in response.text
    assert "Sensitive internal system details" not in response.text
