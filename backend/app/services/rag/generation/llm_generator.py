
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Callable, Optional

from app.services.rag.prompts.rag_prompt import build_rag_prompt
from app.services.rag.retrieval.models import RetrievedChunk


@dataclass
class GenerationResult:
    """
    Represents the result returned by the LLM generation layer.
    """

    answer: str
    prompt: str
    model: str
    metadata: dict


def generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    llm_callable: Optional[Callable[[str], str]] = None,
    model: str = "mock-llm",
) -> GenerationResult:
    """
    Generate an answer using the supplied RAG context.

    The actual LLM provider is injected through llm_callable.
    This keeps the generation layer provider-agnostic.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    prompt = build_rag_prompt(
        query=query,
        chunks=chunks,
    )

    if llm_callable is None:
        answer = (
            "LLM provider is not configured. "
            "The RAG prompt was successfully generated."
        )
    else:
        answer = llm_callable(prompt)

        if not isinstance(answer, str):
            raise TypeError(
                "LLM callable must return a string"
            )

        answer = answer.strip()

    return GenerationResult(
        answer=answer,
        prompt=prompt,
        model=model,
        metadata={
            "query": query.strip(),
            "context_chunks": len(chunks),
        },
    )


def stream_answer(
    query: str,
    chunks: list[RetrievedChunk],
    llm_stream_callable: Optional[
        Callable[[str], Iterator[str]]
    ] = None,
    model: str = "mock-llm",
) -> Iterator[str]:
    """
    Stream an answer using the supplied RAG context.

    The streaming LLM provider is injected through
    llm_stream_callable to keep this layer provider-agnostic.

    Each yielded string represents a generated answer chunk.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    prompt = build_rag_prompt(
        query=query,
        chunks=chunks,
    )

    if llm_stream_callable is None:
        answer = (
            "LLM provider is not configured. "
            "The RAG prompt was successfully generated."
        )
        yield answer
        return

    stream = llm_stream_callable(prompt)

    if stream is None:
        raise TypeError(
            "LLM streaming callable must return an iterator"
        )

    if not hasattr(stream, "__iter__"):
        raise TypeError(
            "LLM streaming callable must return an iterable"
        )

    has_content = False

    for chunk in stream:
        if not isinstance(chunk, str):
            raise TypeError(
                "LLM streaming chunks must be strings"
            )

        if chunk:
            has_content = True
            yield chunk

    if not has_content:
        raise RuntimeError(
            "LLM streaming returned an empty answer"
        )
