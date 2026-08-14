import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

DOCUMENT_ID = "92506777-63d1-4d94-9195-f7619b180965"


@pytest.mark.integration
def test_document_to_rag():
    response = client.post(
        "/api/rag/query",
        json={
            "query": "What does the document say about blind text?",
            "n_results": 5,
            "document_id": DOCUMENT_ID,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["model"] == "qwen3:8b-q4_K_M"
    assert data["answer"].strip()

    assert data["metadata"]["retrieved_results"] > 0
    assert data["metadata"]["reranked_results"] > 0
    assert data["metadata"]["compressed_results"] > 0

    assert data["sources"]

    for source in data["sources"]:
        assert source["document_id"] == DOCUMENT_ID
        assert source["filename"] == "pdflatex-outline.pdf"
        assert source["chunk_id"]