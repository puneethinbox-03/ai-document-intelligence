
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.services.rag.context.compressor import compress_context
from app.services.rag.generation.llm_generator import (
    GenerationResult,
    generate_answer,
    stream_answer,
)
from app.services.rag.reranking.cross_encoder import rerank
from app.services.rag.retrieval.hybrid.hybrid_retriever import (
    retrieve_hybrid,
)
from app.services.rag.relevance.models import RelevanceResult
from app.services.rag.relevance.relevance_service import (
    calculate_relevance,
)
from app.services.rag.retrieval.models import RetrievedChunk


@dataclass
class RAGPipelineResult:
    """
    Represents the complete result of an Intermediate RAG
    pipeline run.
    """

    query: str
    answer: str
    retrieved_chunks: list[RetrievedChunk]
    reranked_chunks: list[RetrievedChunk]
    compressed_chunks: list[RetrievedChunk]
    prompt: str
    model: str
    relevance: RelevanceResult
    metadata: dict[str, Any]


@dataclass
class StreamingRAGPipelineResult:
    """
    Represents the prepared RAG context and token stream
    for a streaming pipeline run.
    """

    query: str
    token_stream: Iterator[str]
    retrieved_chunks: list[RetrievedChunk]
    reranked_chunks: list[RetrievedChunk]
    compressed_chunks: list[RetrievedChunk]
    model: str
    relevance: RelevanceResult
    metadata: dict[str, Any]


def run_rag_pipeline(
    query: str,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
    llm_callable: Optional[Callable[[str], str]] = None,
    model: str = "mock-llm",
    rerank_top_k: Optional[int] = None,
    max_sentences_per_chunk: int = 3,
) -> RAGPipelineResult:
    """
    Execute the complete Intermediate RAG pipeline.

    Pipeline:

        Hybrid Retrieval
              |
        Cross-Encoder Reranking
              |
        Relevance Assessment
              |
        Context Compression
              |
        RAG Prompt Construction
              |
        LLM Generation
    """

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if n_results <= 0:
        raise ValueError(
            "n_results must be greater than zero"
        )

    if rerank_top_k is not None and rerank_top_k <= 0:
        raise ValueError(
            "rerank_top_k must be greater than zero"
        )

    if max_sentences_per_chunk <= 0:
        raise ValueError(
            "max_sentences_per_chunk must be greater than zero"
        )

    clean_query = query.strip()

    # ---------------------------------------------------------
    # 1. Hybrid Retrieval
    # ---------------------------------------------------------

    retrieved_chunks = retrieve_hybrid(
        query=clean_query,
        n_results=n_results,
        where=where,
    )

    # ---------------------------------------------------------
    # 2. Cross-Encoder Reranking
    # ---------------------------------------------------------

    if retrieved_chunks:

        rerank_limit = (
            rerank_top_k
            if rerank_top_k is not None
            else len(retrieved_chunks)
        )

        reranked_chunks = rerank(
            query=clean_query,
            chunks=retrieved_chunks,
            top_k=rerank_limit,
        )

    else:
        reranked_chunks = []

    # ---------------------------------------------------------
    # 3. Relevance Assessment
    # ---------------------------------------------------------

    relevance = calculate_relevance(reranked_chunks)

    # ---------------------------------------------------------
    # 4. Context Compression
    # ---------------------------------------------------------

    if reranked_chunks:

        compressed_chunks = compress_context(
            query=clean_query,
            chunks=reranked_chunks,
            max_sentences_per_chunk=max_sentences_per_chunk,
        )

    else:
        compressed_chunks = []

    # ---------------------------------------------------------
    # 5. LLM Generation
    # ---------------------------------------------------------

    generation_result: GenerationResult = generate_answer(
        query=clean_query,
        chunks=compressed_chunks,
        llm_callable=llm_callable,
        model=model,
    )

    # ---------------------------------------------------------
    # 6. Return Complete Pipeline Result
    # ---------------------------------------------------------

    return RAGPipelineResult(
        query=clean_query,
        answer=generation_result.answer,
        retrieved_chunks=retrieved_chunks,
        reranked_chunks=reranked_chunks,
        compressed_chunks=compressed_chunks,
        prompt=generation_result.prompt,
        model=generation_result.model,
        relevance=relevance,
        metadata={
            "retrieved_results": len(retrieved_chunks),
            "reranked_results": len(reranked_chunks),
            "compressed_results": len(compressed_chunks),
            "model": generation_result.model,
        },
    )


def stream_rag_pipeline(
    query: str,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
    llm_stream_callable: Optional[
        Callable[[str], Iterator[str]]
    ] = None,
    model: str = "mock-llm",
    rerank_top_k: Optional[int] = None,
    max_sentences_per_chunk: int = 3,
) -> StreamingRAGPipelineResult:
    """
    Execute the Intermediate RAG pipeline with streaming generation.

    Retrieval, reranking, relevance assessment and context
    compression run before the token stream is consumed.

    The returned token_stream yields generated text progressively.

    Pipeline:

        Hybrid Retrieval
              |
        Cross-Encoder Reranking
              |
        Relevance Assessment
              |
        Context Compression
              |
        Streaming LLM Generation
    """

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if n_results <= 0:
        raise ValueError(
            "n_results must be greater than zero"
        )

    if rerank_top_k is not None and rerank_top_k <= 0:
        raise ValueError(
            "rerank_top_k must be greater than zero"
        )

    if max_sentences_per_chunk <= 0:
        raise ValueError(
            "max_sentences_per_chunk must be greater than zero"
        )

    clean_query = query.strip()

    # ---------------------------------------------------------
    # 1. Hybrid Retrieval
    # ---------------------------------------------------------

    retrieved_chunks = retrieve_hybrid(
        query=clean_query,
        n_results=n_results,
        where=where,
    )

    # ---------------------------------------------------------
    # 2. Cross-Encoder Reranking
    # ---------------------------------------------------------

    if retrieved_chunks:

        rerank_limit = (
            rerank_top_k
            if rerank_top_k is not None
            else len(retrieved_chunks)
        )

        reranked_chunks = rerank(
            query=clean_query,
            chunks=retrieved_chunks,
            top_k=rerank_limit,
        )

    else:
        reranked_chunks = []

    # ---------------------------------------------------------
    # 3. Relevance Assessment
    # ---------------------------------------------------------

    relevance = calculate_relevance(reranked_chunks)

    # ---------------------------------------------------------
    # 4. Context Compression
    # ---------------------------------------------------------

    if reranked_chunks:

        compressed_chunks = compress_context(
            query=clean_query,
            chunks=reranked_chunks,
            max_sentences_per_chunk=max_sentences_per_chunk,
        )

    else:
        compressed_chunks = []

    # ---------------------------------------------------------
    # 5. Streaming LLM Generation
    # ---------------------------------------------------------

    token_stream = stream_answer(
        query=clean_query,
        chunks=compressed_chunks,
        llm_stream_callable=llm_stream_callable,
        model=model,
    )

    # ---------------------------------------------------------
    # 6. Return Streaming Pipeline Result
    # ---------------------------------------------------------

    return StreamingRAGPipelineResult(
        query=clean_query,
        token_stream=token_stream,
        retrieved_chunks=retrieved_chunks,
        reranked_chunks=reranked_chunks,
        compressed_chunks=compressed_chunks,
        model=model,
        relevance=relevance,
        metadata={
            "retrieved_results": len(retrieved_chunks),
            "reranked_results": len(reranked_chunks),
            "compressed_results": len(compressed_chunks),
            "model": model,
        },
    )
