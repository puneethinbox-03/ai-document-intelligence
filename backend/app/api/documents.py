from fastapi import APIRouter, File, HTTPException, UploadFile
from app.parsers.parser_factory import ParserFactory
from app.schemas.document import (
    DocumentResponse,
    DocumentTextResponse,
)

from app.services.document_service import (
    get_all_documents,
    get_document_by_id,
    get_document_file_path,
    save_uploaded_file,
)

from app.services.extraction_service import (
    extract_document_text,
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


# ============================================================
# Extract Document Text
# ============================================================

@router.get(
    "/{document_id}/text",
    response_model=DocumentTextResponse,
)
def extract_document(
    document_id: str,
):
    # --------------------------------------------------------
    # 1. Find document metadata
    # --------------------------------------------------------

    document = get_document_by_id(
        document_id
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # --------------------------------------------------------
    # 2. Find physical uploaded file
    # --------------------------------------------------------

    file_path = get_document_file_path(
        document_id
    )

    if file_path is None:
        raise HTTPException(
            status_code=404,
            detail="Physical document file not found",
        )

    # --------------------------------------------------------
    # 3. Extract text
    # --------------------------------------------------------

    try:
        text = extract_document_text(
            file_path
        )

        # ----------------------------------------------------
        # 4. Return extracted document text
        # ----------------------------------------------------

        return {
            "document_id": document["document_id"],
            "filename": document["filename"],
            "file_type": document["file_type"],
            "text": text,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document extraction failed: {str(exc)}",
        )

@router.get(
    "/{document_id}/text",
    response_model=DocumentTextResponse,
)
def get_document_text(
    document_id: str,
):
    document = get_document_by_id(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = get_document_file_path(document_id)

    if file_path is None:
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    try:
        parser = ParserFactory.get_parser(file_path)

        raw_text = parser.parse(file_path)

        processed_text = process_text(raw_text)

        return {
            "document_id": document["document_id"],
            "filename": document["filename"],
            "file_type": document["file_type"],
            "text": processed_text,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )