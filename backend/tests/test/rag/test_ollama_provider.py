import pytest

from app.services.rag.generation.ollama_provider import (
    generate_with_ollama,
)


@pytest.mark.integration
def test_ollama_provider():
    answer = generate_with_ollama(
        "Explain Retrieval Augmented Generation in one sentence."
    )

    assert isinstance(answer, str)
    assert answer.strip()