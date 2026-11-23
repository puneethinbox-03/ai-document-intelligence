
import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
)

from app.services.rag.generation.ollama_provider import (
    generate_with_ollama,
    stream_with_ollama,
)

from app.services.rag.pipeline.rag_pipeline import (
    run_rag_pipeline,
    stream_rag_pipeline,
)


router = APIRouter(prefix="/api/rag", tags=["RAG"])


def _mock_llm(prompt: str) -> str:
    return (
        "LLM provider is not configured. "
        "The RAG prompt was successfully generated."
    )


def _mock_llm_stream(prompt: str) -> Iterator[str]:
    """
    Mock streaming provider used when Ollama is not configured.
    """

    yield (
        "LLM provider is not configured. "
        "The RAG prompt was successfully generated."
    )


def _get_llm_provider():
    """
    Return the synchronous LLM provider and model name.
    """

    if settings.rag_llm_provider == "ollama":
        return (
            generate_with_ollama,
            settings.ollama_model,
        )

    return (_mock_llm, "mock-llm")


def _get_llm_stream_provider():
    """
    Return the streaming LLM provider and model name.
    """

    if settings.rag_llm_provider == "ollama":
        return (
            stream_with_ollama,
            settings.ollama_model,
        )

    return (_mock_llm_stream, "mock-llm")


def _build_sources(chunks: list[Any]) -> list[RAGSource]:
    """
    Convert retrieved chunks into API source objects.
    """

    sources: list[RAGSource] = []

    for chunk in chunks:
        sources.append(
            RAGSource(
                document_id=chunk.metadata.get("document_id", "unknown"),
                filename=chunk.metadata.get("filename"),
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.metadata.get("chunk_index"),
            )
        )

    return sources


def _format_sse_event(event: str, data: dict[str, Any]) -> str:
    """
    Format one Server-Sent Event.
    """

    serialized_data = json.dumps(
        jsonable_encoder(data),
        ensure_ascii=False,
    )

    return f"event: {event}\ndata: {serialized_data}\n\n"


@router.post("/query", response_model=RAGQueryResponse)
def query_documents(request: RAGQueryRequest) -> RAGQueryResponse:
    """
    Execute a normal, non-streaming RAG query.
    """

    where = None

    if request.document_id:
        where = {"document_id": request.document_id}

    llm_callable, model = _get_llm_provider()

    result = run_rag_pipeline(
        query=request.query,
        n_results=request.n_results,
        where=where,
        llm_callable=llm_callable,
        model=model,
    )

    sources = _build_sources(result.compressed_chunks)

    return RAGQueryResponse(
        query=result.query,
        answer=result.answer,
        model=result.model,
        sources=sources,
        relevance=result.relevance,
        metadata=result.metadata,
    )


@router.post("/query/stream")
def stream_query_documents(request: RAGQueryRequest) -> StreamingResponse:
    """
    Execute a RAG query and stream the generated answer using SSE.

    Event sequence:
    1. sources
    2. relevance
    3. token (repeated)
    4. complete

    If generation fails, an error event is sent instead of complete.
    """

    where = None

    if request.document_id:
        where = {"document_id": request.document_id}

    llm_stream_callable, model = _get_llm_stream_provider()

    # Retrieval, reranking, relevance assessment and compression
    # happen before the response starts streaming.
    result = stream_rag_pipeline(
        query=request.query,
        n_results=request.n_results,
        where=where,
        llm_stream_callable=llm_stream_callable,
        model=model,
    )

    sources = _build_sources(result.compressed_chunks)

    def event_stream() -> Iterator[str]:
        token_stream = result.token_stream

        try:
            # Send source information first.
            yield _format_sse_event(
                "sources",
                {
                    "sources": sources,
                },
            )

            # Send relevance information before answer generation.
            yield _format_sse_event(
                "relevance",
                {
                    "relevance": result.relevance,
                },
            )

            # Send each generated token as it becomes available.
            for token in token_stream:
                yield _format_sse_event(
                    "token",
                    {
                        "token": token,
                    },
                )

            # Signal successful completion.
            yield _format_sse_event(
                "complete",
                {
                    "query": result.query,
                    "model": result.model,
                    "metadata": result.metadata,
                },
            )

        except Exception as exc:
            # Once streaming has started, report generation errors
            # as SSE events because an HTTP error response is no
            # longer possible.
            yield _format_sse_event(
                "error",
                {
                    "message": str(exc),
                },
            )

        finally:
            # Close the underlying generator when streaming finishes
            # or the client disconnects.
            close_stream = getattr(token_stream, "close", None)

            if callable(close_stream):
                try:
                    close_stream()
                except Exception:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
