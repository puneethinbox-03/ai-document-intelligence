from app.services.rag.reranking.cross_encoder import rerank
from app.services.rag.retrieval.models import RetrievedChunk


def create_test_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="rerank-python",
            text="Python is a programming language used for software development.",
            metadata={"document_id": "rerank-test", "chunk_index": 0},
            score=0.5,
        ),
        RetrievedChunk(
            chunk_id="rerank-sql",
            text="SQL is used to query and manage relational databases.",
            metadata={"document_id": "rerank-test", "chunk_index": 1},
            score=0.4,
        ),
        RetrievedChunk(
            chunk_id="rerank-basketball",
            text="Basketball is a sport played by two teams on a court.",
            metadata={"document_id": "rerank-test", "chunk_index": 2},
            score=0.3,
        ),
    ]


def test_reranker():
    chunks = create_test_chunks()

    results = rerank(
        query="Python programming language",
        chunks=chunks,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk_id == "rerank-python"


def test_reranker_sql():
    chunks = create_test_chunks()

    results = rerank(
        query="SQL relational database",
        chunks=chunks,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].chunk_id == "rerank-sql"


def test_reranker_empty_query():
    chunks = create_test_chunks()

    results = rerank(
        query="",
        chunks=chunks,
        top_k=2,
    )

    assert results == []


def test_reranker_empty_chunks():
    results = rerank(
        query="Python programming",
        chunks=[],
        top_k=2,
    )

    assert results == []


def test_reranker_invalid_top_k():
    chunks = create_test_chunks()

    results = rerank(
        query="Python programming",
        chunks=chunks,
        top_k=0,
    )

    assert results == []


def test_reranker_returns_scores():
    chunks = create_test_chunks()

    results = rerank(
        query="Python programming language",
        chunks=chunks,
        top_k=3,
    )

    assert len(results) == 3
    assert all(result.score is not None for result in results)


def test_reranker_preserves_metadata():
    chunks = create_test_chunks()

    results = rerank(
        query="Python programming",
        chunks=chunks,
        top_k=2,
    )

    python_result = next(
        result
        for result in results
        if result.chunk_id == "rerank-python"
    )

    assert python_result.metadata["document_id"] == "rerank-test"
    assert python_result.metadata["chunk_index"] == 0