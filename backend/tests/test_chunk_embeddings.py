from app.services.chunking.chunk_model import Chunk
from app.services.embeddings.embedding_service import embed_texts


def test_chunk_embeddings():
    chunks = [
        Chunk(
            chunk_id="chunk-1",
            document_id="test-document",
            chunk_index=0,
            text="Python is a programming language.",
            token_count=6,
        ),
        Chunk(
            chunk_id="chunk-2",
            document_id="test-document",
            chunk_index=1,
            text="SQL is used to query relational databases.",
            token_count=8,
        ),
    ]

    embeddings = embed_texts([chunk.text for chunk in chunks])

    assert len(embeddings) == len(chunks)
    assert len(embeddings[0]) == 1024
    assert len(embeddings[1]) == 1024