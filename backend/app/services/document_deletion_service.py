from uuid import UUID

from sqlalchemy.orm import Session

from app.services.document_ownership_service import (
    mark_owned_document_deleting,
    permanently_delete_owned_document,
)
from app.services.document_storage_service import (
    DocumentStorageService,
    document_storage,
)


def delete_owned_document(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
    storage: DocumentStorageService | None = None,
) -> bool:
    """
    Delete an owner's original and sanitized files, then remove
    the PostgreSQL document record.

    The document is first marked as deleting. If file removal or
    database deletion fails, the deleting record remains available
    for a retry.

    Missing files are treated as already deleted.

    Returns False when the document does not exist or is not owned
    by the supplied user.

    This service does not yet remove ChromaDB or BM25 artifacts.
    Those require coordinated cleanup in the indexing/RAG phases.
    """

    storage_service = (
        document_storage if storage is None else storage
    )

    document = mark_owned_document_deleting(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    if document is None:
        return False

    storage_key = document.storage_key

    # Both operations are safe to retry: missing files return False.
    # If the second operation fails, the first can safely be repeated.
    storage_service.delete_original(storage_key)
    storage_service.delete_sanitized(storage_key)

    # Remove the database record only after both file deletions succeed.
    permanently_delete_owned_document(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    return True
