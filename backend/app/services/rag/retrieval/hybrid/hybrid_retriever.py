from typing import Any, Optional

from app.services.rag.retrieval.models import RetrievedChunk
from app.services.rag.retrieval.vector_retriever import retrieve_vector
from app.services.rag.retrieval.keyword.bm25_retriever import retrieve_bm25


def retrieve_hybrid(
    query: str,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
) -> list[RetrievedChunk]:
    """
    Retrieve document chunks using a hybrid
    vector + BM25 retrieval strategy.

    The retriever:
    1. Performs semantic vector retrieval.
    2. Performs BM25 keyword retrieval.
    3. Converts each result's rank into a rank score.
    4. Applies configurable retrieval weights.
    5. Combines duplicate chunks.
    6. Returns the highest-scoring chunks.
    """

    # Validate query.
    if not query or not query.strip():
        return []

    # Validate result count.
    if n_results <= 0:
        return []

    # Validate weights.
    if vector_weight < 0 or keyword_weight < 0:
        raise ValueError(
            "Weights must be non-negative"
        )

    if vector_weight + keyword_weight == 0:
        raise ValueError(
            "At least one retrieval weight must be greater than zero"
        )

    # Retrieve semantic candidates.
    vector_results = retrieve_vector(
        query=query,
        n_results=n_results,
        where=where,
    )

    # Retrieve keyword candidates.
    keyword_results = retrieve_bm25(
        query=query,
        n_results=n_results,
        where=where,
    )

    # Normalize weights.
    total_weight = vector_weight + keyword_weight

    vector_weight = vector_weight / total_weight
    keyword_weight = keyword_weight / total_weight

    # Store unique chunks.
    combined: dict[str, RetrievedChunk] = {}

    # Store fused scores.
    scores: dict[str, float] = {}

    # ---------------------------------------------------------
    # Vector retrieval contribution
    # ---------------------------------------------------------

    for rank, result in enumerate(vector_results):
        rank_score = 1.0 / (rank + 1)

        combined[result.chunk_id] = result

        scores[result.chunk_id] = (
            scores.get(result.chunk_id, 0.0)
            + vector_weight * rank_score
        )

    # ---------------------------------------------------------
    # BM25 retrieval contribution
    # ---------------------------------------------------------

    for rank, result in enumerate(keyword_results):
        rank_score = 1.0 / (rank + 1)

        # Keep the existing result if vector retrieval already
        # returned this chunk.
        if result.chunk_id not in combined:
            combined[result.chunk_id] = result

        scores[result.chunk_id] = (
            scores.get(result.chunk_id, 0.0)
            + keyword_weight * rank_score
        )

    # ---------------------------------------------------------
    # Rank final candidates
    # ---------------------------------------------------------

    ranked_ids = sorted(
        scores,
        key=lambda chunk_id: (
            -scores[chunk_id],
            chunk_id,
        ),
    )

    # ---------------------------------------------------------
    # Build final RetrievedChunk objects
    # ---------------------------------------------------------

    results: list[RetrievedChunk] = []

    for chunk_id in ranked_ids[:n_results]:
        result = combined[chunk_id]

        results.append(
            RetrievedChunk(
                chunk_id=result.chunk_id,
                text=result.text,
                metadata=result.metadata,
                score=scores[chunk_id],
            )
        )

    return results