from app.services.rag.context.compressor import compress_context
from app.services.rag.retrieval.models import RetrievedChunk


def create_test_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="compress-python",
            text=(
                "Python is a programming language. "
                "It is widely used for software development. "
                "The weather is sunny today. "
                "Python supports many libraries."
            ),
            metadata={
                "document_id": "compress-test",
                "chunk_index": 0,
            },
            score=0.9,
        ),
        RetrievedChunk(
            chunk_id="compress-sql",
            text=(
                "SQL is used to query databases. "
                "Relational databases store structured data. "
                "Basketball is a popular sport."
            ),
            metadata={
                "document_id": "compress-test",
                "chunk_index": 1,
            },
            score=0.8,
        ),
    ]


def test_compress_context():
    chunks = create_test_chunks()

    results = compress_context(
        query="Python programming",
        chunks=chunks,
        max_sentences_per_chunk=2,
    )

    assert len(results) == 2
    assert results[0].chunk_id == "compress-python"

    assert "Python" in results[0].text
    assert "programming" in results[0].text


def test_compression_reduces_sentences():
    chunks = create_test_chunks()

    results = compress_context(
        query="Python programming",
        chunks=chunks,
        max_sentences_per_chunk=2,
    )

    python_text = results[0].text

    sentences = [
        sentence.strip()
        for sentence in python_text.split(".")
        if sentence.strip()
    ]

    assert len(sentences) <= 2


def test_compression_preserves_metadata():
    chunks = create_test_chunks()

    results = compress_context(
        query="Python programming",
        chunks=chunks,
        max_sentences_per_chunk=2,
    )

    result = results[0]

    assert result.metadata["document_id"] == "compress-test"
    assert result.metadata["chunk_index"] == 0


def test_compression_preserves_score():
    chunks = create_test_chunks()

    results = compress_context(
        query="Python programming",
        chunks=chunks,
        max_sentences_per_chunk=2,
    )

    assert results[0].score == 0.9


def test_empty_query():
    chunks = create_test_chunks()

    results = compress_context(
        query="",
        chunks=chunks,
    )

    assert results == []


def test_empty_chunks():
    results = compress_context(
        query="Python programming",
        chunks=[],
    )

    assert results == []


def test_invalid_sentence_limit():
    chunks = create_test_chunks()

    results = compress_context(
        query="Python programming",
        chunks=chunks,
        max_sentences_per_chunk=0,
    )

    assert results == []