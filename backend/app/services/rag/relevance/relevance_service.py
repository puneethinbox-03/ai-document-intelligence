from collections.abc import Sequence

from app.services.rag.retrieval.models import RetrievedChunk

from .models import RelevanceResult


# Initial heuristic thresholds.
#
# These are development thresholds, NOT calibrated probabilities.
HIGH_SCORE_THRESHOLD = 0.70
MEDIUM_SCORE_THRESHOLD = 0.40


def _normalize_score(
    score: float,
) -> float:
    """
    Convert a cross-encoder score into a bounded
    relevance signal using a sigmoid.

    This is NOT a calibrated probability.
    """

    import math

    # Clamp extreme values for numerical stability.
    score = max(
        min(score, 20.0),
        -20.0,
    )

    return 1.0 / (
        1.0 + math.exp(-score)
    )


def calculate_relevance(
    chunks: Sequence[RetrievedChunk],
) -> RelevanceResult:
    """
    Calculate retrieval-grounded relevance from
    reranked chunks.

    The strongest signal is the top reranker score.
    """

    if not chunks:
        return RelevanceResult(
            level="low",
            score=0.0,
            evidence_count=0,
            top_rerank_score=None,
        )

    scores = [
        chunk.score
        for chunk in chunks
        if chunk.score is not None
    ]

    if not scores:
        return RelevanceResult(
            level="low",
            score=0.0,
            evidence_count=len(chunks),
            top_rerank_score=None,
        )

    top_score = max(scores)

    normalized_score = _normalize_score(
        top_score
    )

    # Evidence coverage provides a small supporting signal.
    evidence_factor = min(
        len(chunks) / 3.0,
        1.0,
    )

    final_score = (
        normalized_score * 0.85
        + evidence_factor * 0.15
    )

    final_score = max(
        0.0,
        min(final_score, 1.0),
    )

    if final_score >= HIGH_SCORE_THRESHOLD:
        level = "high"
    elif final_score >= MEDIUM_SCORE_THRESHOLD:
        level = "medium"
    else:
        level = "low"

    return RelevanceResult(
        level=level,
        score=round(
            final_score,
            4,
        ),
        evidence_count=len(chunks),
        top_rerank_score=top_score,
    )