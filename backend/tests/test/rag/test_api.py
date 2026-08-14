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