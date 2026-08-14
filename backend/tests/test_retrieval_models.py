from app.services.rag.retrieval.models import RetrievedChunk


def test_retrieved_chunk():
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        text="Python is a programming language.",
        metadata={
            "document_id": "doc-1",
            "chunk_index": 0,
        },
        score=0.95,
    )

    assert chunk.chunk_id == "chunk-1"
    assert chunk.text == "Python is a programming language."
    assert chunk.metadata["document_id"] == "doc-1"
    assert chunk.score == 0.95