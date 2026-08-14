from typing import Sequence

from app.services.rag.retrieval.models import RetrievedChunk


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[RetrievedChunk]],
    k: int = 60,
    n_results: int = 5,
) -> list[RetrievedChunk]:
    """
    Combine multiple ranked retrieval result lists using
    Reciprocal Rank Fusion (RRF).

    RRF score:
        1 / (k + rank)

    Ranks are 1-based.
    """

    if k <= 0:
        raise ValueError("k must be greater than zero")

    if n_results <= 0:
        return []

    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}

    for result_list in result_lists:
        for rank, result in enumerate(result_list, start=1):
            chunk_id = result.chunk_id

            scores[chunk_id] = (
                scores.get(chunk_id, 0.0)
                + 1.0 / (k + rank)
            )

            if chunk_id not in chunks:
                chunks[chunk_id] = result

    ranked_ids = sorted(
        scores,
        key=lambda chunk_id: scores[chunk_id],
        reverse=True,
    )

    fused_results: list[RetrievedChunk] = []

    for chunk_id in ranked_ids[:n_results]:
        result = chunks[chunk_id]

        fused_results.append(
            RetrievedChunk(
                chunk_id=result.chunk_id,
                text=result.text,
                metadata=result.metadata,
                score=scores[chunk_id],
            )
        )

    return fused_results