import pytest

from app.services.rag.generation.llm_generator import (
    GenerationResult,
    generate_answer,
)
from app.services.rag.retrieval.models import RetrievedChunk


def create_test_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="generation-1",
            text="Python is a programming language.",
            metadata={
                "document_id": "doc-generation",
                "chunk_index": 0,
            },
            score=0.95,
        ),
        RetrievedChunk(
            chunk_id="generation-2",
            text="Python is commonly used for software development.",
            metadata={
                "document_id": "doc-generation",
                "chunk_index": 1,
            },
            score=0.90,
        ),
    ]


def test_generate_answer_without_llm():
    chunks = create_test_chunks()

    result = generate_answer(
        query="What is Python?",
        chunks=chunks,
    )

    assert isinstance(result, GenerationResult)

    assert result.answer != ""
    assert result.model == "mock-llm"

    assert "What is Python?" in result.prompt
    assert "Python is a programming language." in result.prompt


def test_generate_answer_with_mock_llm():
    chunks = create_test_chunks()

    def mock_llm(prompt: str) -> str:
        assert "What is Python?" in prompt
        assert "Python is a programming language." in prompt

        return "Python is a programming language."


    result = generate_answer(
        query="What is Python?",
        chunks=chunks,
        llm_callable=mock_llm,
    )

    assert result.answer == "Python is a programming language."


def test_llm_callable_receives_rag_prompt():
    chunks = create_test_chunks()

    received_prompt = {}

    def mock_llm(prompt: str) -> str:
        received_prompt["value"] = prompt
        return "Test answer"

    result = generate_answer(
        query="What is Python?",
        chunks=chunks,
        llm_callable=mock_llm,
    )

    assert result.answer == "Test answer"
    assert "value" in received_prompt
    assert "DOCUMENT CONTEXT:" in received_prompt["value"]
    assert "USER QUESTION:" in received_prompt["value"]


def test_generation_metadata():
    chunks = create_test_chunks()

    result = generate_answer(
        query="What is Python?",
        chunks=chunks,
    )

    assert result.metadata["query"] == "What is Python?"
    assert result.metadata["context_chunks"] == 2


def test_custom_model_name():
    chunks = create_test_chunks()

    result = generate_answer(
        query="What is Python?",
        chunks=chunks,
        model="test-model",
    )

    assert result.model == "test-model"


def test_empty_query():
    chunks = create_test_chunks()

    with pytest.raises(ValueError):
        generate_answer(
            query="",
            chunks=chunks,
        )


def test_whitespace_query():
    chunks = create_test_chunks()

    with pytest.raises(ValueError):
        generate_answer(
            query="   ",
            chunks=chunks,
        )


def test_empty_context():
    result = generate_answer(
        query="What is Python?",
        chunks=[],
    )

    assert result.answer != ""
    assert result.metadata["context_chunks"] == 0
    assert "No relevant document context was retrieved." in result.prompt


def test_llm_return_type_validation():
    chunks = create_test_chunks()

    def invalid_llm(prompt: str):
        return 123

    with pytest.raises(TypeError):
        generate_answer(
            query="What is Python?",
            chunks=chunks,
            llm_callable=invalid_llm,
        )