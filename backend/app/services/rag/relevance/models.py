from typing import Literal

from pydantic import BaseModel, Field


RelevanceLevel = Literal[
    "high",
    "medium",
    "low",
]


class RelevanceResult(BaseModel):
    """
    Retrieval-grounded relevance indicator.

    This is NOT a calibrated probability.
    It is a relative signal derived from
    retrieval/reranking evidence.
    """

    level: RelevanceLevel

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    evidence_count: int = Field(
        ge=0,
    )

    top_rerank_score: float | None = None