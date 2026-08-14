from app.services.rag.retrieval.keyword.bm25_retriever import (
    retrieve_bm25,
)
from app.services.vectorstore.chroma_service import (
    add_chunks,
    get_collection,
)


CHUNK_IDS = [
    "rag-bm25-1",
    "rag-bm25-2",
    "rag-bm25-3",
]

TEXTS = [
    "Python is a programming language used for software development.",
    "SQL is used to query and manage relational databases.",
    "Basketball is a popular sport played around the world.",
]

METADATAS = [
    {
        "document_id": "rag-bm25-test",
        "chunk_index": 0,
    },
    {
        "document_id": "rag-bm25-test",
        "chunk_index": 1,
    },
    {
        "document_id": "rag-bm25-test",
        "chunk_index": 2,
    },
]


def setup_test_chunks():
    """
    Insert isolated test chunks into ChromaDB.

    BM25 itself does not use embeddings, but the ChromaDB
    storage layer requires embeddings when adding chunks.
    """

    collection = get_collection()

    # Remove previous test data if it exists.
    collection.delete(ids=CHUNK_IDS)

    # ChromaDB collection uses 1024-dimensional embeddings.
    embeddings = [
        [0.1] * 1024,
        [0.2] * 1024,
        [0.3] * 1024,
    ]

    add_chunks(
        chunk_ids=CHUNK_IDS,
        texts=TEXTS,
        embeddings=embeddings,
        metadatas=METADATAS,
    )


def test_bm25_retriever():
    """
    Test BM25 retrieval for a Python-related query.
    """

    setup_test_chunks()

    results = retrieve_bm25(
        query="Python programming",
        n_results=2,
        where={
            "document_id": "rag-bm25-test",
        },
    )

    assert len(results) == 2

    # Python chunk should be ranked first.
    assert results[0].chunk_id == "rag-bm25-1"

    # All results must belong to our test chunks.
    assert all(
        result.chunk_id in CHUNK_IDS
        for result in results
    )


def test_bm25_sql_search():
    """
    Test BM25 retrieval for an SQL-related query.
    """

    setup_test_chunks()

    results = retrieve_bm25(
        query="SQL database",
        n_results=2,
        where={
            "document_id": "rag-bm25-test",
        },
    )

    assert len(results) == 2

    # SQL chunk should be ranked first.
    assert results[0].chunk_id == "rag-bm25-2"

    # All results must belong to our test chunks.
    assert all(
        result.chunk_id in CHUNK_IDS
        for result in results
    )


def test_bm25_empty_query():
    """
    Empty query should return an empty result list.
    """

    setup_test_chunks()

    results = retrieve_bm25(
        query="",
        n_results=5,
    )

    assert results == []


def test_bm25_top_k():
    """
    BM25 should respect the requested number of results.
    """

    setup_test_chunks()

    results = retrieve_bm25(
        query="Python",
        n_results=1,
        where={
            "document_id": "rag-bm25-test",
        },
    )

    assert len(results) == 1


def test_bm25_metadata_filter():
    """
    Test BM25 metadata filtering.
    """

    setup_test_chunks()

    results = retrieve_bm25(
        query="Python",
        n_results=5,
        where={
            "document_id": "rag-bm25-test",
        },
    )

    assert len(results) >= 1

    assert all(
        result.metadata["document_id"] == "rag-bm25-test"
        for result in results
    )