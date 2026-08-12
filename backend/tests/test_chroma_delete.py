from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import (
    add_chunks,
    get_chunks,
    delete_chunks,
)


def test_delete_chunks():

    texts = [
        "Temporary document chunk."
    ]

    embeddings = embed_texts(texts)

    chunk_id = "delete-test-chunk"

    add_chunks(
        chunk_ids=[chunk_id],
        texts=texts,
        embeddings=embeddings,
        metadatas=[
            {
                "document_id": "delete-test-document",
                "chunk_index": 0,
            }
        ],
    )

    result = get_chunks([chunk_id])

    assert chunk_id in result["ids"]

    delete_chunks([chunk_id])

    result = get_chunks([chunk_id])

    assert result["ids"] == []