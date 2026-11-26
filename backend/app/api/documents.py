
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
)
from app.services.document_ownership_service import (
    create_owned_document,
    get_owned_document,
    list_owned_documents,
)
from app.services.document_deletion_service import delete_owned_document
from app.services.document_storage_service import document_storage
from app.services.extraction_service import extract_document_text


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


def _document_response(document) -> DocumentResponse:
    return DocumentResponse(
        document_id=str(document.id),
        filename=document.original_filename,
        file_type=Path(document.original_filename).suffix.lower().lstrip("."),
        file_size=document.file_size_bytes,
        status=document.status,
    )


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
    """Store an original document and create its owner-specific database record."""

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

    try:
        document = create_owned_document(
            db,
            owner_id=current_user.id,
            original_filename=stored_document.original_filename,
            storage_key=stored_document.storage_key,
            content_type=stored_document.content_type,
            file_size_bytes=stored_document.file_size_bytes,
            sha256_hash=stored_document.sha256_hash,
        )

    except Exception:
        try:
            document_storage.delete_original(
                stored_document.storage_key
            )
        except Exception:
            logger.error(
                "Original document cleanup failed after database error"
            )

        logger.error("Document database record creation failed")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload could not be completed.",
        ) from None

    return _document_response(document)


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
