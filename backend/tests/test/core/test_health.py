from fastapi.testclient import TestClient

from app.main import app
from app.api import health


client = TestClient(app)


def test_health_endpoint_returns_healthy_without_chromadb(
    monkeypatch,
):
    def unexpected_chromadb_access():
        raise AssertionError(
            "Liveness endpoint should not access ChromaDB"
        )

    monkeypatch.setattr(
        health,
        "get_chroma_client",
        unexpected_chromadb_access,
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy"
    }


def test_readiness_endpoint_returns_ready_when_chromadb_is_healthy(
    monkeypatch,
):
    class MockChromaClient:
        def heartbeat(self):
            return 123456789

    monkeypatch.setattr(
        health,
        "get_chroma_client",
        lambda: MockChromaClient(),
    )

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "chromadb": "healthy"
        },
    }


def test_readiness_endpoint_returns_503_when_chromadb_is_unavailable(
    monkeypatch,
):
    def unavailable_chromadb():
        raise RuntimeError(
            "Internal ChromaDB connection details"
        )

    monkeypatch.setattr(
        health,
        "get_chroma_client",
        unavailable_chromadb,
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "chromadb": "unavailable"
        },
    }

    assert (
        "Internal ChromaDB connection details"
        not in response.text
    )
