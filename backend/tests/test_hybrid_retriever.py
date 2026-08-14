from app.services.embeddings.embedding_service import embed_texts
from app.services.rag.retrieval.hybrid.hybrid_retriever import retrieve_hybrid
from app.services.vectorstore.chroma_service import (
    add_chunks,
    get_collection,
)


TEST_DOCUMENT_ID = "rag-hybrid-test"


def setup_test_chunks():
    """
    Insert isolated test chunks for hybrid retrieval tests.

    A unique document_id is used so that old chunks already
    stored in persistent ChromaDB do not affect the tests.
    """

    chunk_ids = [
        "rag-hybrid-1",
        "rag-hybrid-2",
        "rag-hybrid-3",
    ]

    texts = [
        "Python is a programming language used for software development.",
        "SQL is used to query relational databases.",
        "Basketball is a popular sport played around the world.",
    ]

    embeddings = embed_texts(texts)

    metadatas = [
        {
            "document_id": TEST_DOCUMENT_ID,
            "chunk_index": 0,
        },
        {
            "document_id": TEST_DOCUMENT_ID,
            "chunk_index": 1,
        },
        {
            "document_id": TEST_DOCUMENT_ID,
            "chunk_index": 2,
        },
    ]

    collection = get_collection()

    # Remove previous copies of these test chunks if they exist.
    collection.delete(ids=chunk_ids)

    add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def cleanup_test_chunks():
    """
    Remove test chunks after each test.
    """

    collection = get_collection()

    collection.delete(
        ids=[
            "rag-hybrid-1",
            "rag-hybrid-2",
            "rag-hybrid-3",
        ]
    )


def test_hybrid_retriever():
    setup_test_chunks()

    results = retrieve_hybrid(
        query="Python programming",
        n_results=2,
        where={
            "document_id": TEST_DOCUMENT_ID,
        },
    )

    assert len(results) == 2

    result_ids = [result.chunk_id for result in results]

    assert "rag-hybrid-1" in result_ids

    cleanup_test_chunks()


def test_hybrid_sql_search():
    setup_test_chunks()

    results = retrieve_hybrid(
        query="SQL database",
        n_results=2,
        where={
            "document_id": TEST_DOCUMENT_ID,
        },
    )

    assert len(results) == 2

    result_ids = [result.chunk_id for result in results]

    assert "rag-hybrid-2" in result_ids

    cleanup_test_chunks()


def test_hybrid_empty_query():
    results = retrieve_hybrid(
        query="",
        n_results=2,
    )

    assert results == []


def test_hybrid_invalid_n_results():
    results = retrieve_hybrid(
        query="Python programming",
        n_results=0,
    )

    assert results == []


def test_hybrid_metadata_filter():
    setup_test_chunks()

    results = retrieve_hybrid(
        query="Python programming",
        n_results=5,
        where={
            "document_id": TEST_DOCUMENT_ID,
        },
    )

    assert len(results) <= 5

    for result in results:
        assert result.metadata["document_id"] == TEST_DOCUMENT_ID

    cleanup_test_chunks()