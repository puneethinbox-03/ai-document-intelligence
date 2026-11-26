from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document


VALID_DOCUMENT_STATUSES = {
    "uploaded",
    "validating",
    "queued",
    "processing",
    "indexed",
    "failed",
    "deleting",
    "deleted",
}


def create_owned_document(
    db: Session,
    *,
    owner_id: UUID,
    original_filename: str,
    storage_key: str,
    content_type: str,
    file_size_bytes: int,
    sha256_hash: str | None = None,
) -> Document:
    """
    Create a document record for the authenticated owner.

    The owner ID must come from the authenticated user, not
    from untrusted request data.
    """

    document = Document(
        user_id=owner_id,
        original_filename=original_filename,
        storage_key=storage_key,
        content_type=content_type,
        file_size_bytes=file_size_bytes,
        sha256_hash=sha256_hash,
        status="uploaded",
    )

    try:
        db.add(document)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise

    return document


def get_owned_document(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
) -> Document | None:
    """
    Retrieve a document only if it belongs to the specified owner.

    Returns None for both missing documents and documents owned
    by another user. This avoids revealing another user's records.
    """

    return db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == owner_id,
        )
    )


def list_owned_documents(
    db: Session,
    *,
    owner_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[Document]:
    """
    Return only the specified owner's documents.

    Results are ordered newest first and support pagination.
    """

    if skip < 0:
        raise ValueError("skip cannot be negative")

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    statement = (
        select(Document)
        .where(Document.user_id == owner_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def update_owned_document_status(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> Document | None:
    """
    Update a document's status only if it belongs to the owner.

    Returns None when the document does not exist or is not owned
    by the specified user.
    """

    if status not in VALID_DOCUMENT_STATUSES:
        raise ValueError("Invalid document status")

    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    if document is None:
        return None

    document.status = status
    document.error_code = error_code
    document.error_message = error_message

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return document


def mark_owned_document_deleting(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
) -> Document | None:
    """
    Mark an owner's document as deleting.

    The status is committed before file deletion begins so that
    an interrupted deletion can be identified and retried.

    Returns None if the document does not belong to the owner.
    """

    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    if document is None:
        return None

    if document.status != "deleting":
        document.status = "deleting"
        document.error_code = None
        document.error_message = None

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return document


def permanently_delete_owned_document(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
) -> bool:
    """
    Permanently remove an owned document database record.

    Only documents already marked as deleting can be removed.
    Existing database relationships cascade to chat associations
    and processing-job records.

    Returns False if the document no longer exists or is not owned
    by the specified user.
    """

    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    if document is None:
        return False

    if document.status != "deleting":
        raise ValueError(
            "Document must be marked as deleting before removal."
        )

    try:
        db.delete(document)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return True
