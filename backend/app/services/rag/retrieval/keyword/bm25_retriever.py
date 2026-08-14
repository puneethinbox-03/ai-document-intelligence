from typing import List, Optional

from rank_bm25 import BM25Okapi

from app.services.rag.retrieval.models import RetrievedChunk
from app.services.vectorstore.chroma_service import get_chunks


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text for BM25 retrieval.
    """
    return text.lower().split()


def retrieve_bm25(
    query: str,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> List[RetrievedChunk]:
    """
    Retrieve document chunks using BM25 keyword search.
    """

    if not query or not query.strip():
        return []

    if n_results <= 0:
        return []

    chunks = get_chunks()

    ids = chunks.get("ids", [])
    documents = chunks.get("documents", [])
    metadatas = chunks.get("metadatas", [])

    if not ids or not documents:
        return []

    # Apply metadata filtering before BM25 indexing.
    if where:
        filtered_ids = []
        filtered_documents = []
        filtered_metadatas = []

        for chunk_id, document, metadata in zip(
            ids,
            documents,
            metadatas,
        ):
            if all(
                metadata.get(key) == value
                for key, value in where.items()
            ):
                filtered_ids.append(chunk_id)
                filtered_documents.append(document)
                filtered_metadatas.append(metadata)

        ids = filtered_ids
        documents = filtered_documents
        metadatas = filtered_metadatas

    if not documents:
        return []

    # Tokenize all documents.
    tokenized_documents = [
        _tokenize(document)
        for document in documents
    ]

    # Build BM25 index.
    bm25 = BM25Okapi(tokenized_documents)

    # Tokenize user query.
    query_tokens = _tokenize(query)

    # Calculate BM25 relevance scores.
    scores = bm25.get_scores(query_tokens)

    # Rank documents from highest score to lowest.
    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )

    results: List[RetrievedChunk] = []

    for index in ranked_indexes[:n_results]:
        results.append(
            RetrievedChunk(
                chunk_id=ids[index],
                text=documents[index],
                metadata=metadatas[index],
                score=float(scores[index]),
            )
        )

    return results