from dataclasses import dataclass
from pathlib import Path

from app.services.chunking.chunking_service import chunk_text
from app.services.embeddings.embedding_service import embed_texts
from app.services.extraction_service import extract_document_text
from app.services.vectorstore.chroma_service import (
    add_chunks,
    delete_chunks,
    get_chunks,
)


@dataclass
class IndexingResult:
    """
    Result returned after indexing a document.
    """

    document_id: str
    chunk_count: int
    token_count: int


def _delete_existing_document_chunks(
    document_id: str,
) -> None:
    """
    Remove existing ChromaDB chunks belonging to a document.

    This makes re-indexing safe and prevents duplicate chunks.
    """

    stored_chunks = get_chunks()

    ids = stored_chunks.get("ids", [])
    metadatas = stored_chunks.get("metadatas", [])

    existing_ids = []

    for chunk_id, metadata in zip(
        ids,
        metadatas,
    ):
        if metadata.get("document_id") == document_id:
            existing_ids.append(chunk_id)

    if existing_ids:
        delete_chunks(existing_ids)


def index_document(
    file_path: Path,
    document_id: str,
    filename: str | None = None,
) -> IndexingResult:
    """
    Extract, chunk, embed, and store a document in ChromaDB.

    Pipeline:

        File
          ↓
        Extraction
          ↓
        Chunking
          ↓
        Embeddings
          ↓
        ChromaDB
    """

    if not document_id or not document_id.strip():
        raise ValueError("document_id is required")

    if not file_path.exists():
        raise FileNotFoundError(
            f"Document file not found: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Document path is not a file: {file_path}"
        )

    clean_document_id = document_id.strip()

    # ---------------------------------------------------------
    # 1. Extract and process text
    # ---------------------------------------------------------

    text = extract_document_text(
        file_path
    )

    if not text or not text.strip():
        _delete_existing_document_chunks(
            clean_document_id
        )

        return IndexingResult(
            document_id=clean_document_id,
            chunk_count=0,
            token_count=0,
        )

    # ---------------------------------------------------------
    # 2. Create chunks
    # ---------------------------------------------------------

    chunks = chunk_text(
        text=text,
        document_id=clean_document_id,
    )

    if not chunks:
        _delete_existing_document_chunks(
            clean_document_id
        )

        return IndexingResult(
            document_id=clean_document_id,
            chunk_count=0,
            token_count=0,
        )

    # ---------------------------------------------------------
    # 3. Generate embeddings
    # ---------------------------------------------------------

    chunk_texts = [
        chunk.text
        for chunk in chunks
    ]

    embeddings = embed_texts(
        chunk_texts
    )

    if len(embeddings) != len(chunks):
        raise ValueError(
            "Embedding count does not match chunk count"
        )

    # ---------------------------------------------------------
    # 4. Prepare stable chunk IDs and metadata
    # ---------------------------------------------------------

    chunk_ids = []
    metadatas = []

    for chunk in chunks:
        # Use deterministic IDs instead of UUIDs generated
        # by chunking_service so re-indexing is predictable.
        chunk_id = (
            f"{clean_document_id}-{chunk.chunk_index}"
        )

        chunk_ids.append(chunk_id)

        metadata = {
            "document_id": clean_document_id,
            "chunk_index": chunk.chunk_index,
            "token_count": chunk.token_count,
        }

        if filename:
            metadata["filename"] = filename

        metadatas.append(metadata)

    # ---------------------------------------------------------
    # 5. Verify embeddings before modifying ChromaDB
    # ---------------------------------------------------------

    for embedding in embeddings:
        if len(embedding) != 1024:
            raise ValueError(
                "Embedding dimension must be 1024"
            )

    # ---------------------------------------------------------
    # 6. Remove previous version of this document
    # ---------------------------------------------------------

    _delete_existing_document_chunks(
        clean_document_id
    )

    # ---------------------------------------------------------
    # 7. Store new chunks in ChromaDB
    # ---------------------------------------------------------

    add_chunks(
        chunk_ids=chunk_ids,
        texts=chunk_texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # ---------------------------------------------------------
    # 8. Return indexing result
    # ---------------------------------------------------------

    total_tokens = sum(
        chunk.token_count
        for chunk in chunks
    )

    return IndexingResult(
        document_id=clean_document_id,
        chunk_count=len(chunks),
        token_count=total_tokens,
    )