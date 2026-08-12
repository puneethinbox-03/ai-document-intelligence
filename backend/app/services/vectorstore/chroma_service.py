from typing import List, Optional

from .chroma_client import get_chroma_client


COLLECTION_NAME = "document_chunks"


def get_collection():
    """
    Get or create the document chunks collection.
    """

    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine"
        }
    )


def add_chunks(
    chunk_ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
    metadatas: List[dict],
):
    """
    Add document chunks and their embeddings to ChromaDB.
    """

    if not chunk_ids:
        return

    if not (
        len(chunk_ids)
        == len(texts)
        == len(embeddings)
        == len(metadatas)
    ):
        raise ValueError(
            "chunk_ids, texts, embeddings and metadatas "
            "must have the same length"
        )

    collection = get_collection()

    collection.add(
        ids=chunk_ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def query_chunks(
    query_embedding: List[float],
    n_results: int = 5,
    where: Optional[dict] = None,
):
    """
    Search ChromaDB for the most similar document chunks.
    """

    collection = get_collection()

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
    )


def search_chunks(
    query_embedding: List[float],
    n_results: int = 5,
    where: Optional[dict] = None,
):
    """
    Application-level wrapper for semantic chunk search.
    """

    if not query_embedding:
        return {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    return query_chunks(
        query_embedding=query_embedding,
        n_results=n_results,
        where=where,
    )


def get_chunks(
    chunk_ids: Optional[List[str]] = None,
    include_embeddings: bool = False,
):
    """
    Retrieve stored chunks.

    If chunk_ids are provided, retrieve only those chunks.
    Otherwise retrieve all chunks.

    Embeddings are returned only when include_embeddings=True.
    """

    collection = get_collection()

    include = [
        "documents",
        "metadatas",
    ]

    if include_embeddings:
        include.append("embeddings")

    if chunk_ids:
        return collection.get(
            ids=chunk_ids,
            include=include,
        )

    return collection.get(
        include=include,
    )


def delete_chunks(
    chunk_ids: List[str],
):
    """
    Delete chunks from ChromaDB.
    """

    if not chunk_ids:
        return

    collection = get_collection()

    collection.delete(
        ids=chunk_ids
    )


def count_chunks() -> int:
    """
    Return the number of chunks currently stored.
    """

    collection = get_collection()

    return collection.count()