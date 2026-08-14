from typing import List

from sentence_transformers import CrossEncoder

from app.services.rag.retrieval.models import RetrievedChunk


# Cross-encoder model used for reranking.
# This is a lightweight and commonly used model for a RAG POC.
MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    """
    Load the cross-encoder model lazily.

    The model is loaded only when reranking is actually required.
    """

    global _model

    if _model is None:
        _model = CrossEncoder(MODEL_NAME)

    return _model


def rerank(
    query: str,
    chunks: List[RetrievedChunk],
    top_k: int = 5,
) -> List[RetrievedChunk]:
    """
    Rerank retrieved document chunks using a cross-encoder.

    Args:
        query:
            User's search/query text.

        chunks:
            Candidate chunks returned by a retriever/fusion stage.

        top_k:
            Maximum number of chunks to return.

    Returns:
        Reranked list of RetrievedChunk objects with updated scores.
    """

    if not query or not query.strip():
        return []

    if not chunks:
        return []

    if top_k <= 0:
        return []

    model = _get_model()

    # Create query-document pairs for the cross-encoder.
    pairs = [
        (query, chunk.text)
        for chunk in chunks
    ]

    # Generate relevance scores.
    scores = model.predict(pairs)

    # Combine chunks with their cross-encoder scores.
    scored_chunks = list(zip(chunks, scores))

    # Highest score = most relevant.
    scored_chunks.sort(
        key=lambda item: float(item[1]),
        reverse=True,
    )

    results: List[RetrievedChunk] = []

    for chunk, score in scored_chunks[:top_k]:
        results.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
                score=float(score),
            )
        )

    return results