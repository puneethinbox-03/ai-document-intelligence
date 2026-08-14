from typing import Any

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """
    Request model for RAG queries.
    """

    query: str = Field(
        ...,
        min_length=1,
        description="User question",
    )

    n_results: int = Field(
        default=5,
        gt=0,
        description="Number of retrieval results",
    )

    document_id: str | None = Field(
        default=None,
        description="Optional document ID to restrict retrieval",
    )


class RAGSource(BaseModel):
    """
    Source chunk used to generate the RAG response.
    """

    document_id: str
    filename: str | None = None
    chunk_id: str
    chunk_index: int | None = None


class RAGQueryResponse(BaseModel):
    """
    Response model returned by the RAG API.
    """

    query: str
    answer: str
    model: str
    sources: list[RAGSource]
    metadata: dict[str, Any]