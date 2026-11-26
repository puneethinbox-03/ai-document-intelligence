from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.services.document_storage_service import (
    DocumentStorageService,
)


@pytest.fixture
def storage(tmp_path: Path) -> DocumentStorageService:
    return DocumentStorageService(
        original_dir=tmp_path / "original",
        sanitized_dir=tmp_path / "sanitized",
        max_file_size_bytes=1024,
    )


def make_upload(
    filename: str,
    content: bytes,
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


@pytest.mark.anyio
async def test_save_original_success(storage):
    content = b"sample document content"
    upload = make_upload("report.pdf", content)

    stored = await storage.save_original(upload)

    saved_path = storage.get_original_path(stored.storage_key)

    assert saved_path.exists()
    assert saved_path.read_bytes() == content
    assert stored.original_filename == "report.pdf"
    assert stored.content_type == "application/pdf"
    assert stored.file_size_bytes == len(content)
    assert stored.sha256_hash == sha256(content).hexdigest()
    assert stored.storage_key.endswith(".pdf")
    assert stored.storage_key != "report.pdf"


@pytest.mark.anyio
async def test_save_original_strips_client_path(storage):
    upload = make_upload(
        r"C:\private\folder\report.pdf",
        b"document",
    )

    stored = await storage.save_original(upload)

    assert stored.original_filename == "report.pdf"


@pytest.mark.anyio
async def test_save_original_rejects_missing_filename(storage):
    upload = make_upload("", b"document")

    with pytest.raises(ValueError, match="valid filename"):
        await storage.save_original(upload)


@pytest.mark.anyio
async def test_save_original_rejects_unsupported_extension(storage):
    upload = make_upload("malware.exe", b"content")

    with pytest.raises(ValueError, match="Unsupported document file type"):
        await storage.save_original(upload)


@pytest.mark.anyio
async def test_save_original_rejects_empty_file(storage):
    upload = make_upload("empty.pdf", b"")

    with pytest.raises(ValueError, match="empty"):
        await storage.save_original(upload)


@pytest.mark.anyio
async def test_save_original_rejects_oversized_file(storage):
    upload = make_upload("large.pdf", b"x" * 1025)

    with pytest.raises(ValueError, match="maximum allowed file size"):
        await storage.save_original(upload)

    assert list(storage.original_dir.glob("*.uploading")) == []


def test_storage_rejects_invalid_storage_key(storage):
    invalid_keys = [
        "",
        ".",
        "..",
        "../outside.pdf",
        r"..\outside.pdf",
        "folder/file.pdf",
    ]

    for key in invalid_keys:
        with pytest.raises(ValueError, match="Invalid storage key"):
            storage.get_original_path(key)


def test_original_and_sanitized_directories_are_separate(storage):
    assert storage.original_dir != storage.sanitized_dir
    assert storage.original_dir.parent == storage.sanitized_dir.parent


def test_delete_original(storage):
    storage.original_dir.mkdir(parents=True, exist_ok=True)
    path = storage.original_dir / "original.pdf"
    path.write_bytes(b"original")

    assert storage.delete_original("original.pdf") is True
    assert not path.exists()
    assert storage.delete_original("original.pdf") is False


def test_delete_sanitized(storage):
    storage.sanitized_dir.mkdir(parents=True, exist_ok=True)
    path = storage.sanitized_dir / "sanitized.txt"
    path.write_bytes(b"sanitized")

    assert storage.delete_sanitized("sanitized.txt") is True
    assert not path.exists()
    assert storage.delete_sanitized("sanitized.txt") is False


def test_storage_rejects_unsupported_backend(tmp_path):
    with pytest.raises(RuntimeError, match="not supported"):
        DocumentStorageService(
            original_dir=tmp_path / "original",
            sanitized_dir=tmp_path / "sanitized",
            storage_backend="cloud",
        )


def test_storage_rejects_invalid_maximum_file_size(tmp_path):
    with pytest.raises(ValueError, match="greater than zero"):
        DocumentStorageService(
            original_dir=tmp_path / "original",
            sanitized_dir=tmp_path / "sanitized",
            max_file_size_bytes=0,
        )
from unittest.mock import patch


@pytest.mark.anyio
async def test_save_original_closes_upload_after_success(storage):
    upload = make_upload("report.pdf", b"document")

    await storage.save_original(upload)

    assert upload.file.closed is True


@pytest.mark.anyio
async def test_save_original_closes_upload_after_failure(storage):
    upload = make_upload("invalid.exe", b"document")

    with pytest.raises(ValueError):
        await storage.save_original(upload)

    assert upload.file.closed is True


@pytest.mark.anyio
async def test_save_original_removes_temporary_file_after_write_failure(storage):
    upload = make_upload("report.pdf", b"document")

    original_open = Path.open

    def failing_open(path, *args, **kwargs):
        if path.name.endswith(".uploading"):
            raise OSError("Simulated storage write failure")

        return original_open(path, *args, **kwargs)

    with patch.object(Path, "open", failing_open):
        with pytest.raises(OSError, match="Simulated storage write failure"):
            await storage.save_original(upload)

    assert upload.file.closed is True
    assert list(storage.original_dir.glob("*.uploading")) == []
    assert list(storage.original_dir.glob("*.pdf")) == []
