from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
    ".pptx",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
}

CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class StoredDocument:
    """Information about a successfully stored original document."""

    storage_key: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    sha256_hash: str


class DocumentStorageService:
    """
    Private local document storage.

    Original files are stored separately from sanitized derivatives.
    Database metadata and ownership are managed by separate services.
    """

    def __init__(
        self,
        *,
        original_dir: Path | None = None,
        sanitized_dir: Path | None = None,
        max_file_size_bytes: int | None = None,
        storage_backend: str | None = None,
    ) -> None:
        self.storage_backend = (
            storage_backend or settings.storage_backend
        )

        if self.storage_backend != "local":
            raise RuntimeError(
                "The configured document storage backend is not supported."
            )

        self.original_dir = (
            original_dir or settings.upload_dir
        ).resolve()

        self.sanitized_dir = (
            sanitized_dir or settings.sanitized_dir
        ).resolve()

        self.max_file_size_bytes = (
            max_file_size_bytes
            if max_file_size_bytes is not None
            else settings.max_file_size_mb * 1024 * 1024
        )

        if self.max_file_size_bytes <= 0:
            raise ValueError(
                "Maximum file size must be greater than zero."
            )

    @staticmethod
    def _validate_filename(filename: str | None) -> str:
        """Return a safe filename without any client-supplied path."""

        if not filename or "\x00" in filename:
            raise ValueError("A valid filename is required.")

        normalized = filename.replace("\\", "/")
        safe_filename = PurePosixPath(normalized).name

        if not safe_filename or safe_filename in {".", ".."}:
            raise ValueError("A valid filename is required.")

        if len(safe_filename) > 255:
            raise ValueError("Filename is too long.")

        extension = Path(safe_filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported document file type.")

        return safe_filename

    @staticmethod
    def _resolve_storage_path(
        storage_dir: Path,
        storage_key: str,
    ) -> Path:
        """Resolve a storage key without allowing path traversal."""

        if (
            not storage_key
            or storage_key in {".", ".."}
            or "/" in storage_key
            or "\\" in storage_key
        ):
            raise ValueError("Invalid storage key.")

        root = storage_dir.resolve()
        candidate = (root / storage_key).resolve()

        if candidate.parent != root:
            raise ValueError("Invalid storage key.")

        return candidate

    async def save_original(
        self,
        upload: UploadFile,
    ) -> StoredDocument:
        """
        Stream an uploaded file into private storage.

        The upload is always closed, including when validation fails.
        Temporary files are removed if storage fails.
        """

        temporary_path: Path | None = None

        try:
            original_filename = self._validate_filename(
                upload.filename
            )

            content_type = (
                upload.content_type or "application/octet-stream"
            )

            if len(content_type) > 127:
                raise ValueError("Invalid content type.")

            extension = Path(original_filename).suffix.lower()
            storage_key = f"{uuid4().hex}{extension}"

            self.original_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            final_path = self._resolve_storage_path(
                self.original_dir,
                storage_key,
            )

            temporary_key = f".{uuid4().hex}.uploading"
            temporary_path = self._resolve_storage_path(
                self.original_dir,
                temporary_key,
            )

            total_size = 0
            file_hash = sha256()

            with temporary_path.open("xb") as destination:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)

                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > self.max_file_size_bytes:
                        raise ValueError(
                            "Document exceeds the maximum allowed file size."
                        )

                    destination.write(chunk)
                    file_hash.update(chunk)

            if total_size == 0:
                raise ValueError("Uploaded document is empty.")

            if final_path.exists():
                raise FileExistsError(
                    "Generated storage key already exists."
                )

            temporary_path.replace(final_path)
            temporary_path = None

            return StoredDocument(
                storage_key=storage_key,
                original_filename=original_filename,
                content_type=content_type,
                file_size_bytes=total_size,
                sha256_hash=file_hash.hexdigest(),
            )

        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

            raise

        finally:
            await upload.close()

    def get_original_path(self, storage_key: str) -> Path:
        """Resolve the private original file path."""
        return self._resolve_storage_path(
            self.original_dir,
            storage_key,
        )

    def get_sanitized_path(self, storage_key: str) -> Path:
        """Resolve a sanitized derivative path."""
        return self._resolve_storage_path(
            self.sanitized_dir,
            storage_key,
        )

    def delete_original(self, storage_key: str) -> bool:
        """Delete an original file if it exists."""

        path = self.get_original_path(storage_key)

        if not path.is_file():
            return False

        path.unlink(missing_ok=True)
        return True

    def delete_sanitized(self, storage_key: str) -> bool:
        """Delete a sanitized derivative if it exists."""

        path = self.get_sanitized_path(storage_key)

        if not path.is_file():
            return False

        path.unlink(missing_ok=True)
        return True


document_storage = DocumentStorageService()
