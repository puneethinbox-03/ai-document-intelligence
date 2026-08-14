from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document import (
    DocumentResponse,
    DocumentTextResponse,
)

from app.services.document_service import (
    get_all_documents,
    get_document_by_id,
    get_document_file_path,
    save_uploaded_file,
    update_document_status,
)

from app.services.extraction_service import (
    extract_document_text,
)

from app.services.indexing_service import (
    index_document,
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
    """
    Upload, index, and store a document.

    Flow:
        Upload
          ↓
        Save file
          ↓
        Processing
          ↓
        Extract text
          ↓
        Chunk text
          ↓
        Generate embeddings
          ↓
        Store in ChromaDB
          ↓
        Indexed
    """

    document = None

    try:
        # ----------------------------------------------------
        # 1. Save uploaded file
        # ----------------------------------------------------

        document = await save_uploaded_file(file)

        document_id = document["document_id"]

        # ----------------------------------------------------
        # 2. Mark document as processing
        # ----------------------------------------------------

        update_document_status(
            document_id=document_id,
            status="processing",
        )

        # ----------------------------------------------------
        # 3. Find physical uploaded file
        # ----------------------------------------------------

        file_path = get_document_file_path(
            document_id
        )

        if file_path is None:
            raise ValueError(
                "Uploaded file could not be located"
            )

        # ----------------------------------------------------
        # 4. Index document
        # ----------------------------------------------------

        index_document(
            file_path=file_path,
            document_id=document_id,
            filename=document["filename"],
        )

        # ----------------------------------------------------
        # 5. Mark document as indexed
        # ----------------------------------------------------

        updated_document = update_document_status(
            document_id=document_id,
            status="indexed",
        )

        return updated_document or document

    except ValueError as exc:
        # ----------------------------------------------------
        # Validation / indexing error
        # ----------------------------------------------------

        if document is not None:
            update_document_status(
                document_id=document["document_id"],
                status="failed",
                error=str(exc),
            )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        # ----------------------------------------------------
        # Unexpected indexing error
        # ----------------------------------------------------

        if document is not None:
            update_document_status(
                document_id=document["document_id"],
                status="failed",
                error=str(exc),
            )

        raise HTTPException(
            status_code=500,
            detail=f"Document indexing failed: {str(exc)}",
        )


# ============================================================
# List All Documents
# ============================================================

@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents():
    """
    Return all uploaded documents.
    """

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
    """
    Return a document by its document ID.
    """

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
    """
    Extract and return processed text for a document.
    """

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
    # 3. Extract and process text
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