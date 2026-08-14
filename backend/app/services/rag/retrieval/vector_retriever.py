from typing import Any, Optional

from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import search_chunks

from .models import RetrievedChunk


def retrieve_vector(
    query: str,
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
) -> list[RetrievedChunk]:
    """
    Retrieve document chunks using semantic vector search.
    """

    if not query or not query.strip():
        return []

    query_embedding = embed_texts([query])[0]

    results = search_chunks(
        query_embedding=query_embedding,
        n_results=n_results,
        where=where,
    )

    chunks: list[RetrievedChunk] = []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for index, chunk_id in enumerate(ids):
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=documents[index],
                metadata=metadatas[index] or {},
                score=distances[index] if distances else None,
            )
        )

    return chunks