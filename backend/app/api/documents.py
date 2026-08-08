from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document import DocumentResponse
from app.services.document_service import (
    get_all_documents,
    get_document_by_id,
    save_uploaded_file,
)


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


# ============================================================
# Upload Document
# ============================================================

@router.post(
    "/upload",
    response_model=DocumentResponse,
)
async def upload_document(
    file: UploadFile = File(...),
):
    try:
        document = await save_uploaded_file(file)
        return document

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# List All Documents
# ============================================================

@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents():
    return get_all_documents()


# ============================================================
# Get Document By ID
# ============================================================

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: str,
):
    document = get_document_by_id(
        document_id
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return document