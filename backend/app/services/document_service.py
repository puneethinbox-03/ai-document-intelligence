import json
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


# ============================================================
# Configuration
# ============================================================

UPLOAD_DIR = Path("uploads")
METADATA_FILE = UPLOAD_DIR / "metadata.json"

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
    ".zip",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ============================================================
# File Helpers
# ============================================================

def get_file_extension(filename: str) -> str:
    """
    Get the file extension in lowercase.

    Example:
        document.PDF -> .pdf
    """
    return Path(filename).suffix.lower()


# ============================================================
# Metadata Helpers
# ============================================================

def load_metadata() -> list:
    """
    Load document metadata from metadata.json.

    Returns:
        list: List of uploaded document metadata.
    """

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not METADATA_FILE.exists():
        return []

    try:
        with METADATA_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return []


def save_metadata(documents: list) -> None:
    """
    Save document metadata to metadata.json.
    """

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with METADATA_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            documents,
            file,
            indent=4,
        )


def get_all_documents() -> list:
    """
    Return all uploaded document metadata.
    """

    return load_metadata()


def get_document_by_id(
    document_id: str,
) -> dict | None:
    """
    Find a document by its document ID.

    Returns:
        Document metadata if found.
        None if not found.
    """

    documents = load_metadata()

    for document in documents:
        if document["document_id"] == document_id:
            return document

    return None


def get_document_file_path(document_id: str) -> Path | None:
    """
    Find the physical uploaded file using its document ID.
    """

    documents = load_metadata()

    for document in documents:
        if document["document_id"] == document_id:

            extension = get_file_extension(
                document["filename"]
            )

            file_path = UPLOAD_DIR / f"{document_id}{extension}"

            if file_path.exists():
                return file_path

    return None
# ============================================================
# Upload Service
# ============================================================

async def save_uploaded_file(
    file: UploadFile,
) -> dict:
    """
    Validate and save an uploaded document.

    Returns:
        dict: Document metadata.
    """

    # --------------------------------------------------------
    # 1. Validate filename
    # --------------------------------------------------------

    if not file.filename:
        raise ValueError("Filename is required")

    # --------------------------------------------------------
    # 2. Validate file extension
    # --------------------------------------------------------

    extension = get_file_extension(
        file.filename
    )

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: "
            f"{extension or 'unknown'}"
        )

    # --------------------------------------------------------
    # 3. Read file
    # --------------------------------------------------------

    file_content = await file.read()

    # --------------------------------------------------------
    # 4. Validate file size
    # --------------------------------------------------------

    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(
            "File size exceeds the 50 MB limit"
        )

    # --------------------------------------------------------
    # 5. Generate unique document ID
    # --------------------------------------------------------

    document_id = str(uuid4())

    # --------------------------------------------------------
    # 6. Create upload directory
    # --------------------------------------------------------

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 7. Create stored filename
    # --------------------------------------------------------

    stored_filename = (
        f"{document_id}{extension}"
    )

    file_path = (
        UPLOAD_DIR / stored_filename
    )

    # --------------------------------------------------------
    # 8. Save physical file
    # --------------------------------------------------------

    file_path.write_bytes(
        file_content
    )

    # --------------------------------------------------------
    # 9. Create document metadata
    # --------------------------------------------------------

    document = {
        "document_id": document_id,
        "filename": file.filename,
        "file_type": extension.lstrip("."),
        "file_size": len(file_content),
        "status": "uploaded",
    }

    # --------------------------------------------------------
    # 10. Save metadata
    # --------------------------------------------------------

    documents = load_metadata()

    documents.append(document)

    save_metadata(documents)

    # --------------------------------------------------------
    # 11. Return metadata
    # --------------------------------------------------------

    return document