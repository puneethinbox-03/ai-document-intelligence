from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import (
    add_chunks,
    get_collection,
)

from app.services.rag.retrieval.vector_retriever import retrieve_vector


def test_vector_retriever():
    chunk_ids = [
        "rag-vector-1",
        "rag-vector-2",
        "rag-vector-3",
    ]

    texts = [
        "Python is a programming language used for software development.",
        "SQL is used to query relational databases.",
        "Basketball is a popular sport played around the world.",
    ]

    embeddings = embed_texts(texts)

    metadatas = [
        {
            "document_id": "rag-vector-test",
            "chunk_index": 0,
        },
        {
            "document_id": "rag-vector-test",
            "chunk_index": 1,
        },
        {
            "document_id": "rag-vector-test",
            "chunk_index": 2,
        },
    ]

    collection = get_collection()

    collection.delete(ids=chunk_ids)

    add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    results = retrieve_vector(
        query="programming language",
        n_results=2,
        where={
            "document_id": "rag-vector-test",
        },
    )

    assert len(results) == 2

    assert all(
        result.chunk_id in chunk_ids
        for result in results
    )

    assert any(
        "Python" in result.text
        for result in results
    )