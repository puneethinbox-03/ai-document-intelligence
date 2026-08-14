import os

from fastapi import APIRouter

from app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSource,
)

from app.services.rag.generation.ollama_provider import (
    generate_with_ollama,
)

from app.services.rag.pipeline.rag_pipeline import (
    run_rag_pipeline,
)


router = APIRouter(
    prefix="/api/rag",
    tags=["RAG"],
)


def _mock_llm(prompt: str) -> str:
    """
    Deterministic mock LLM used for tests.
    """

    return (
        "LLM provider is not configured. "
        "The RAG prompt was successfully generated."
    )


def _get_llm_provider():
    """
    Select the configured LLM provider.

    Supported:
        mock
        ollama
    """

    provider = os.getenv(
        "RAG_LLM_PROVIDER",
        "mock",
    ).strip().lower()

    if provider == "ollama":
        return (
            generate_with_ollama,
            os.getenv(
                "OLLAMA_MODEL",
                "qwen3:8b-q4_K_M",
            ),
        )

    return (
        _mock_llm,
        "mock-llm",
    )


@router.post(
    "/query",
    response_model=RAGQueryResponse,
)
def query_documents(
    request: RAGQueryRequest,
) -> RAGQueryResponse:
    """
    Execute the RAG pipeline for a user query.
    """

    where = None

    if request.document_id:
        where = {
            "document_id": request.document_id,
        }

    llm_callable, model = _get_llm_provider()

    result = run_rag_pipeline(
        query=request.query,
        n_results=request.n_results,
        where=where,
        llm_callable=llm_callable,
        model=model,
    )

    sources: list[RAGSource] = []

    for chunk in result.compressed_chunks:
        sources.append(
            RAGSource(
                document_id=chunk.metadata.get(
                    "document_id",
                    "unknown",
                ),
                filename=chunk.metadata.get(
                    "filename",
                ),
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.metadata.get(
                    "chunk_index",
                ),
            )
        )

    return RAGQueryResponse(
        query=result.query,
        answer=result.answer,
        model=result.model,
        sources=sources,
        metadata=result.metadata,
    )