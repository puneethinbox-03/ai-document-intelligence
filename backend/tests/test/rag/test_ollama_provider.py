
import pytest

from app.services.rag.generation.ollama_provider import (
    generate_with_ollama,
    stream_with_ollama,
)


# ============================================================
# Existing Ollama integration test
# ============================================================


@pytest.mark.integration
def test_ollama_provider():
    answer = generate_with_ollama(
        "Explain Retrieval Augmented Generation in one sentence."
    )

    assert isinstance(answer, str)
    assert answer.strip()


# ============================================================
# Ollama streaming provider unit tests
# ============================================================


def test_ollama_stream_provider(monkeypatch):
    """
    Verify Ollama streaming returns multiple text chunks.
    """

    def mock_ollama_chat(**kwargs):
        assert kwargs["stream"] is True

        return iter(
            [
                {
                    "message": {
                        "content": "Retrieval ",
                    }
                },
                {
                    "message": {
                        "content": "Augmented ",
                    }
                },
                {
                    "message": {
                        "content": "Generation",
                    }
                },
            ]
        )

    monkeypatch.setattr(
        "app.services.rag.generation.ollama_provider.ollama_client.chat",
        mock_ollama_chat,
    )

    chunks = list(
        stream_with_ollama(
            "Explain RAG."
        )
    )

    assert chunks == [
        "Retrieval ",
        "Augmented ",
        "Generation",
    ]


def test_ollama_stream_skips_empty_chunks(monkeypatch):
    """
    Verify empty chunks are ignored when other content exists.
    """

    def mock_ollama_chat(**kwargs):
        return iter(
            [
                {
                    "message": {
                        "content": "",
                    }
                },
                {
                    "message": {
                        "content": "Hello",
                    }
                },
                {
                    "message": {
                        "content": "",
                    }
                },
            ]
        )

    monkeypatch.setattr(
        "app.services.rag.generation.ollama_provider.ollama_client.chat",
        mock_ollama_chat,
    )

    chunks = list(
        stream_with_ollama("Test prompt")
    )

    assert chunks == ["Hello"]


def test_ollama_stream_empty_prompt():
    """
    Verify empty prompts are rejected.
    """

    with pytest.raises(
        ValueError,
        match="Prompt cannot be empty",
    ):
        list(
            stream_with_ollama("")
        )


def test_ollama_stream_invalid_chunk_type(monkeypatch):
    """
    Verify non-string streaming content is rejected.
    """

    def mock_ollama_chat(**kwargs):
        return iter(
            [
                {
                    "message": {
                        "content": 123,
                    }
                }
            ]
        )

    monkeypatch.setattr(
        "app.services.rag.generation.ollama_provider.ollama_client.chat",
        mock_ollama_chat,
    )

    with pytest.raises(
        TypeError,
        match="Ollama streaming content must be a string",
    ):
        list(
            stream_with_ollama("Test prompt")
        )


def test_ollama_stream_empty_response(monkeypatch):
    """
    Verify an empty Ollama streaming response raises an error.
    """

    def mock_ollama_chat(**kwargs):
        return iter([])

    monkeypatch.setattr(
        "app.services.rag.generation.ollama_provider.ollama_client.chat",
        mock_ollama_chat,
    )

    with pytest.raises(
        RuntimeError,
        match="Ollama returned an empty streaming response",
    ):
        list(
            stream_with_ollama("Test prompt")
        )


def test_ollama_stream_provider_error(monkeypatch):
    """
    Verify Ollama connection/provider errors are wrapped.
    """

    def mock_ollama_chat(**kwargs):
        raise ConnectionError(
            "Ollama server is unavailable"
        )

    monkeypatch.setattr(
        "app.services.rag.generation.ollama_provider.ollama_client.chat",
        mock_ollama_chat,
    )

    with pytest.raises(
        RuntimeError,
        match="Ollama streaming failed",
    ):
        list(
            stream_with_ollama("Test prompt")
        )
