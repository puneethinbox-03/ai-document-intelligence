
import logging
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_csrf
from app.models import User
from app.schemas.document import (
    DocumentResponse,
    DocumentTextResponse,
    DocumentProcessingJobResponse,
)
from app.services.document_ownership_service import (
    get_owned_document,
    list_owned_documents,
)
from app.services.document_deletion_service import delete_owned_document
from app.services.document_storage_service import document_storage
from app.services.extraction_service import extract_document_text
from app.services.document_job_service import (
    create_owned_document_with_processing_job,
    get_owned_processing_job,
    list_owned_processing_jobs,
)
from app.services.outbox_dispatcher_service import (
    dispatch_pending_document_jobs,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


# Only approved, generic error messages are returned to API clients.
# Raw database error messages are never exposed.
SAFE_JOB_ERROR_MESSAGES = {
    "DOCUMENT_UNAVAILABLE": "Document is unavailable for processing",
    "PROCESSING_FAILED": "Document processing failed",
    "SENSITIVE_DATA_SCAN_FAILED": "Document security validation failed",
    "SANITIZATION_FAILED": "Document security validation failed",
    "INDEXING_FAILED": "Document indexing failed",
    "QUEUE_UNAVAILABLE": "Background processing is temporarily unavailable",
}


def _document_response(document) -> DocumentResponse:
    return DocumentResponse(
        document_id=str(document.id),
        filename=document.original_filename,
        file_type=Path(document.original_filename).suffix.lower().lstrip("."),
        file_size=document.file_size_bytes,
        status=document.status,
    )


def _processing_job_response(job) -> DocumentProcessingJobResponse:
    """Build a safe processing-job API response."""

    safe_error_message = SAFE_JOB_ERROR_MESSAGES.get(
        job.error_code
    )

    return DocumentProcessingJobResponse(
        job_id=str(job.id),
        document_id=str(job.document_id),
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        available_at=job.available_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_code=(
            job.error_code
            if safe_error_message is not None
            else None
        ),
        error_message=safe_error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ---------------------------------------------------------------------------
# Document upload and background processing
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Store an original document and atomically create its
    owner-specific database record and processing job.

    Redis receives only the processing-job UUID.
    """

    # Step 1: Store the original document in private storage.
    try:
        stored_document = await document_storage.save_original(file)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    except Exception:
        logger.error("Document storage operation failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload could not be completed.",
        ) from None

    # Step 2: Create the document and processing job
    # in one PostgreSQL transaction.
    try:
        document, processing_job = (
            create_owned_document_with_processing_job(
                db,
                owner_id=current_user.id,
                original_filename=stored_document.original_filename,
                storage_key=stored_document.storage_key,
                content_type=stored_document.content_type,
                file_size_bytes=stored_document.file_size_bytes,
                sha256_hash=stored_document.sha256_hash,
            )
        )

    except Exception:
        # The database transaction failed.
        # Remove the original file because no database record
        # was successfully committed.
        try:
            document_storage.delete_original(
                stored_document.storage_key
            )

        except Exception:
            logger.error(
                "Original document cleanup failed after database error"
            )

        logger.error(
            "Document and processing job database creation failed"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload could not be completed.",
        ) from None

    # Step 3: Best-effort delivery from the committed outbox.
    #
    # The dispatcher uses its own short-lived database sessions.
    # Redis receives only processing-job and dispatch UUIDs.
    #
    # A dispatch failure must not undo a successful upload.
    # The persistent outbox record remains available for retry.
    try:
        dispatch_pending_document_jobs(batch_size=10)

    except Exception:
        logger.error(
            "Document processing outbox dispatch deferred",
            extra={
                "event": "document_outbox_dispatch_deferred",
            },
        )

    return _document_response(document)


# ---------------------------------------------------------------------------
# List documents
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a paginated list of the authenticated user's documents."""

    documents = list_owned_documents(
        db,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
    )

    return [
        _document_response(document)
        for document in documents
    ]


# ---------------------------------------------------------------------------
# Document processing job status
# ---------------------------------------------------------------------------

@router.get(
    "/{document_id}/jobs",
    response_model=list[DocumentProcessingJobResponse],
)
def list_document_processing_jobs(
    document_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return processing jobs belonging to an owned document.

    Jobs belonging to other users are never exposed.
    """

    # Verify document ownership first.
    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    jobs = list_owned_processing_jobs(
        db,
        document_id=document_id,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
    )

    return [
        _processing_job_response(job)
        for job in jobs
    ]


@router.get(
    "/{document_id}/jobs/{job_id}",
    response_model=DocumentProcessingJobResponse,
)
def get_document_processing_job(
    document_id: UUID,
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return one processing job belonging to an owned document.

    Both document ownership and job-to-document association
    are verified.
    """

    # First verify document ownership.
    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Then verify job ownership.
    job = get_owned_processing_job(
        db,
        processing_job_id=job_id,
        owner_id=current_user.id,
    )

    # A job belonging to a different document must not be returned.
    if job is None or job.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return _processing_job_response(job)


# ---------------------------------------------------------------------------
# Get document metadata
# ---------------------------------------------------------------------------

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a document only when it belongs to the authenticated user."""

    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return _document_response(document)


# ---------------------------------------------------------------------------
# Download original document
# ---------------------------------------------------------------------------

@router.get(
    "/{document_id}/download",
    response_class=FileResponse,
)
def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download an original document after verifying ownership."""

    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        file_path = document_storage.get_original_path(
            document.storage_key
        )

    except ValueError:
        logger.error("Invalid document storage key")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        ) from None

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.original_filename,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


# ---------------------------------------------------------------------------
# Extract document text
# ---------------------------------------------------------------------------

@router.get(
    "/{document_id}/text",
    response_model=DocumentTextResponse,
)
def extract_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract text after verifying document ownership."""

    document = get_owned_document(
        db,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    file_path = document_storage.get_original_path(
        document.storage_key
    )

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    try:
        extracted_text = extract_document_text(file_path)

        return DocumentTextResponse(
            document_id=str(document.id),
            filename=document.original_filename,
            file_type=Path(
                document.original_filename
            ).suffix.lower().lstrip("."),
            text=extracted_text,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document text could not be extracted.",
        ) from None

    except Exception:
        logger.error("Document text extraction failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document text extraction failed.",
        ) from None


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_csrf)],
)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an owned document and its stored files."""

    try:
        deleted = delete_owned_document(
            db,
            document_id=document_id,
            owner_id=current_user.id,
        )

    except Exception:
        logger.error("Document deletion failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document deletion failed.",
        ) from None

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
