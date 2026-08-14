import pytest

from app.services.rag.prompts.rag_prompt import (
    SYSTEM_PROMPT,
    build_rag_prompt,
)
from app.services.rag.retrieval.models import RetrievedChunk


def create_test_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="prompt-chunk-1",
            text="Python is a programming language.",
            metadata={
                "document_id": "doc-1",
                "chunk_index": 0,
            },
            score=0.95,
        ),
        RetrievedChunk(
            chunk_id="prompt-chunk-2",
            text="Python is commonly used for software development.",
            metadata={
                "document_id": "doc-1",
                "chunk_index": 1,
            },
            score=0.90,
        ),
    ]


def test_build_rag_prompt():
    chunks = create_test_chunks()

    prompt = build_rag_prompt(
        query="What is Python?",
        chunks=chunks,
    )

    assert isinstance(prompt, str)
    assert "What is Python?" in prompt
    assert "Python is a programming language." in prompt


def test_prompt_contains_system_instructions():
    chunks = create_test_chunks()

    prompt = build_rag_prompt(
        query="What is Python?",
        chunks=chunks,
    )

    assert SYSTEM_PROMPT in prompt
    assert "provided document context" in prompt


def test_prompt_contains_document_metadata():
    chunks = create_test_chunks()

    prompt = build_rag_prompt(
        query="What is Python?",
        chunks=chunks,
    )

    assert "doc-1" in prompt
    assert "Chunk Index: 0" in prompt
    assert "Chunk Index: 1" in prompt
    assert "prompt-chunk-1" in prompt
    assert "prompt-chunk-2" in prompt


def test_prompt_contains_all_context():
    chunks = create_test_chunks()

    prompt = build_rag_prompt(
        query="What is Python?",
        chunks=chunks,
    )

    assert "Python is a programming language." in prompt
    assert (
        "Python is commonly used for software development."
        in prompt
    )


def test_empty_chunks():
    prompt = build_rag_prompt(
        query="What is Python?",
        chunks=[],
    )

    assert "No relevant document context was retrieved." in prompt
    assert "What is Python?" in prompt


def test_empty_query():
    chunks = create_test_chunks()

    with pytest.raises(ValueError):
        build_rag_prompt(
            query="",
            chunks=chunks,
        )


def test_whitespace_query():
    chunks = create_test_chunks()

    with pytest.raises(ValueError):
        build_rag_prompt(
            query="   ",
            chunks=chunks,
        )