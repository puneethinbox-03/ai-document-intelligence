from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import (
    add_chunks,
    delete_chunks,
    get_chunks,
)


def test_add_and_get_chunks():

    chunk_ids = [
        "test-chroma-store-1",
        "test-chroma-store-2",
    ]

    texts = [
        "Python is a programming language.",
        "SQL is used for querying databases.",
    ]

    # Generate real 1024-dimensional embeddings
    embeddings = embed_texts(texts)

    metadatas = [
        {
            "document_id": "test-document",
            "chunk_index": 0,
        },
        {
            "document_id": "test-document",
            "chunk_index": 1,
        },
    ]

    # Remove previous test data if it exists
    delete_chunks(chunk_ids)

    # Add chunks to ChromaDB
    add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # Retrieve chunks
    result = get_chunks(chunk_ids)

    # Verify IDs
    assert len(result["ids"]) == 2
    assert result["ids"][0] == "test-chroma-store-1"
    assert result["ids"][1] == "test-chroma-store-2"

    # Verify documents
    assert result["documents"][0] == "Python is a programming language."
    assert result["documents"][1] == "SQL is used for querying databases."

    # Verify metadata
    assert result["metadatas"][0]["document_id"] == "test-document"
    assert result["metadatas"][1]["document_id"] == "test-document"

    # Cleanup test data
    delete_chunks(chunk_ids)