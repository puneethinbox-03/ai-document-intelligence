
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def use_mock_llm(monkeypatch):
    """
    Force API tests to use the deterministic mock LLM.

    Real Ollama integration is tested separately in
    test_ollama_provider.py.
    """

    monkeypatch.setenv(
        "RAG_LLM_PROVIDER",
        "mock",
    )


# ============================================================
# Existing synchronous RAG API tests
# ============================================================


def test_rag_query_endpoint():
    response = client.post(
        "/api/rag/query",
        json={
            "query": "What is Python?",
            "n_results": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == "What is Python?"
    assert "answer" in data
    assert "model" in data
    assert "sources" in data
    assert "metadata" in data

    assert data["model"] == "mock-llm"


def test_rag_query_empty_query():
    response = client.post(
        "/api/rag/query",
        json={
            "query": "",
            "n_results": 5,
        },
    )

    assert response.status_code == 422


def test_rag_query_missing_query():
    response = client.post(
        "/api/rag/query",
        json={
            "n_results": 5,
        },
    )

    assert response.status_code == 422


def test_rag_query_invalid_n_results():
    response = client.post(
        "/api/rag/query",
        json={
            "query": "Python",
            "n_results": 0,
        },
    )

    assert response.status_code == 422


def test_rag_query_with_document_id():
    response = client.post(
        "/api/rag/query",
        json={
            "query": "What is this document about?",
            "n_results": 5,
            "document_id": (
                "92506777-63d1-4d94-9195-f7619b180965"
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["query"] == (
        "What is this document about?"
    )

    assert data["model"] == "mock-llm"

    assert "sources" in data
    assert isinstance(
        data["sources"],
        list,
    )

    assert data["metadata"][
        "retrieved_results"
    ] == 2

    assert data["metadata"][
        "reranked_results"
    ] == 2

    assert data["metadata"][
        "compressed_results"
    ] == 2

    for source in data["sources"]:
        assert source["document_id"] == (
            "92506777-63d1-4d94-9195-f7619b180965"
        )


# ============================================================
# Streaming API test helpers
# ============================================================


def _parse_sse_events(response_text: str) -> list[dict]:
    """
    Parse Server-Sent Events from the response body.
    """

    events = []

    for block in response_text.strip().split("\n\n"):
        if not block.strip():
            continue

        event_name = None
        event_data = None

        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()

            elif line.startswith("data:"):
                event_data = json.loads(
                    line[len("data:"):].strip()
                )

        if event_name is not None:
            events.append(
                {
                    "event": event_name,
                    "data": event_data,
                }
            )

    return events


def _create_mock_streaming_result(token_stream):
    """
    Create a mock result returned by stream_rag_pipeline().
    """

    mock_chunk = SimpleNamespace(
        metadata={
            "document_id": "test-document-123",
            "filename": "python-guide.pdf",
            "chunk_index": 2,
        },
        chunk_id="chunk-123",
    )

    return SimpleNamespace(
        query="What is Python?",
        token_stream=token_stream,
        compressed_chunks=[
            mock_chunk,
        ],
        relevance={
            "is_relevant": True,
        },
        model="mock-llm",
        metadata={
            "retrieved_results": 5,
            "reranked_results": 3,
            "compressed_results": 1,
        },
    )


# ============================================================
# New streaming RAG API tests
# ============================================================


def test_rag_stream_endpoint_event_order(monkeypatch):
    """
    Verify the streaming endpoint sends events in the
    expected order and returns the generated tokens.
    """

    def mock_stream_pipeline(**kwargs):
        return _create_mock_streaming_result(
            iter(
                [
                    "Python ",
                    "is ",
                    "a programming language.",
                ]
            )
        )

    monkeypatch.setattr(
        "app.api.rag.stream_rag_pipeline",
        mock_stream_pipeline,
    )

    response = client.post(
        "/api/rag/query/stream",
        json={
            "query": "What is Python?",
            "n_results": 5,
        },
    )

    assert response.status_code == 200

    assert response.headers[
        "content-type"
    ].startswith("text/event-stream")

    events = _parse_sse_events(
        response.text
    )

    event_names = [
        item["event"]
        for item in events
    ]

    assert event_names == [
        "sources",
        "relevance",
        "token",
        "token",
        "token",
        "complete",
    ]

    # Verify source information.
    assert events[0]["data"]["sources"][0][
        "document_id"
    ] == "test-document-123"

    assert events[0]["data"]["sources"][0][
        "filename"
    ] == "python-guide.pdf"

    # Verify relevance information.
    assert events[1]["data"]["relevance"][
        "is_relevant"
    ] is True

    # Verify streamed tokens.
    streamed_tokens = [
        item["data"]["token"]
        for item in events
        if item["event"] == "token"
    ]

    assert streamed_tokens == [
        "Python ",
        "is ",
        "a programming language.",
    ]

    # Verify completion information.
    assert events[-1]["data"]["query"] == (
        "What is Python?"
    )

    assert events[-1]["data"]["model"] == "mock-llm"


def test_rag_stream_endpoint_with_document_id(monkeypatch):
    """
    Verify document_id is passed to the streaming pipeline.
    """

    captured_arguments = {}

    def mock_stream_pipeline(**kwargs):
        captured_arguments.update(kwargs)

        return _create_mock_streaming_result(
            iter(
                [
                    "Document-specific answer."
                ]
            )
        )

    monkeypatch.setattr(
        "app.api.rag.stream_rag_pipeline",
        mock_stream_pipeline,
    )

    response = client.post(
        "/api/rag/query/stream",
        json={
            "query": "What is this document about?",
            "n_results": 5,
            "document_id": "test-document-123",
        },
    )

    assert response.status_code == 200

    assert captured_arguments["where"] == {
        "document_id": "test-document-123",
    }

    events = _parse_sse_events(
        response.text
    )

    assert events[0]["event"] == "sources"

    assert events[0]["data"]["sources"][0][
        "document_id"
    ] == "test-document-123"


def test_rag_stream_endpoint_generation_error(monkeypatch):
    """
    Verify generation failures are returned as SSE error events.
    """

    def failing_token_stream():
        yield "Partial answer "

        raise RuntimeError(
            "Mock generation failure"
        )

    def mock_stream_pipeline(**kwargs):
        return _create_mock_streaming_result(
            failing_token_stream()
        )

    monkeypatch.setattr(
        "app.api.rag.stream_rag_pipeline",
        mock_stream_pipeline,
    )

    response = client.post(
        "/api/rag/query/stream",
        json={
            "query": "What is Python?",
            "n_results": 5,
        },
    )

    assert response.status_code == 200

    events = _parse_sse_events(
        response.text
    )

    event_names = [
        item["event"]
        for item in events
    ]

    assert event_names == [
        "sources",
        "relevance",
        "token",
        "error",
    ]

    assert events[2]["data"]["token"] == (
        "Partial answer "
    )

    assert events[-1]["data"]["message"] == (
        "Mock generation failure"
    )

    assert "complete" not in event_names


def test_rag_stream_endpoint_empty_query():
    """
    Verify an empty query is rejected.
    """

    response = client.post(
        "/api/rag/query/stream",
        json={
            "query": "",
            "n_results": 5,
        },
    )

    assert response.status_code == 422


def test_rag_stream_endpoint_invalid_n_results():
    """
    Verify invalid n_results is rejected.
    """

    response = client.post(
        "/api/rag/query/stream",
        json={
            "query": "What is Python?",
            "n_results": 0,
        },
    )

    assert response.status_code == 422
