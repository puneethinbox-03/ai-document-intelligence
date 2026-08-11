from app.services.chunking.chunking_service import (
    chunk_text,
    count_tokens,
)


def test_count_tokens():
    text = "Hello world"
    assert count_tokens(text) > 0


def test_empty_text():
    chunks = chunk_text("", "doc-1")
    assert chunks == []


def test_chunking_creates_chunks():
    text = "This is a test sentence. " * 5000

    chunks = chunk_text(text, "doc-1")

    assert len(chunks) > 1


def test_document_id():
    text = "This is a test sentence. " * 2000

    chunks = chunk_text(text, "doc-123")

    assert all(chunk.document_id == "doc-123" for chunk in chunks)


def test_chunk_indexes():
    text = "This is a test sentence. " * 3000

    chunks = chunk_text(text, "doc-1")

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_token_count():
    text = "This is a test sentence. " * 3000

    chunks = chunk_text(text, "doc-1")

    for chunk in chunks:
        assert chunk.token_count > 0


def test_invalid_overlap():
    text = "Hello world"

    try:
        chunk_text(text, "doc-1", chunk_size=100, chunk_overlap=100)
        assert False
    except ValueError:
        assert True