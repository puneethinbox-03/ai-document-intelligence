import pytest

from app.services.rag.pipeline.rag_pipeline import (
    RAGPipelineResult,
    run_rag_pipeline,
)


def test_empty_query():
    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        run_rag_pipeline("")


def test_whitespace_query():
    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        run_rag_pipeline("   ")


def test_invalid_n_results():
    with pytest.raises(
        ValueError,
        match="n_results must be greater than zero",
    ):
        run_rag_pipeline(
            query="Python",
            n_results=0,
        )


def test_pipeline_result_structure():
    result = run_rag_pipeline(
        query="Python programming",
        n_results=2,
    )

    assert isinstance(result, RAGPipelineResult)

    assert result.query == "Python programming"
    assert isinstance(result.answer, str)
    assert isinstance(result.retrieved_chunks, list)
    assert isinstance(result.reranked_chunks, list)
    assert isinstance(result.compressed_chunks, list)
    assert isinstance(result.prompt, str)
    assert isinstance(result.model, str)
    assert isinstance(result.metadata, dict)


def test_pipeline_result_counts():
    result = run_rag_pipeline(
        query="Python programming",
        n_results=2,
    )

    assert result.metadata["retrieved_results"] == len(
        result.retrieved_chunks
    )

    assert result.metadata["reranked_results"] == len(
        result.reranked_chunks
    )

    assert result.metadata["compressed_results"] == len(
        result.compressed_chunks
    )


def test_pipeline_query_is_trimmed():
    result = run_rag_pipeline(
        query="   Python programming   ",
        n_results=2,
    )

    assert result.query == "Python programming"


def test_pipeline_mock_generation():
    result = run_rag_pipeline(
        query="Python programming",
        n_results=2,
    )

    assert result.model == "mock-llm"

    assert (
        "LLM provider is not configured"
        in result.answer
    )


def test_pipeline_prompt_contains_query():
    result = run_rag_pipeline(
        query="Python programming",
        n_results=2,
    )

    assert "Python programming" in result.prompt


def test_pipeline_custom_llm():
    def fake_llm(prompt: str) -> str:
        assert "Python programming" in prompt
        return "Python is a programming language."

    result = run_rag_pipeline(
        query="Python programming",
        n_results=2,
        llm_callable=fake_llm,
        model="test-llm",
    )

    assert result.answer == (
        "Python is a programming language."
    )

    assert result.model == "test-llm"