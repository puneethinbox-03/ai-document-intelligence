from app.services.embeddings.embedding_service import embed_text
from app.services.vectorstore.chroma_service import (
    add_chunks,
    search_chunks,
)


def test_semantic_search():

    texts = [
        "Python is a programming language used for software development.",
        "SQL is used to query and manage relational databases.",
        "Basketball is a popular sport played around the world.",
    ]

    chunk_ids = [
        "search-test-python",
        "search-test-sql",
        "search-test-basketball",
    ]

    embeddings = [
        embed_text(text)
        for text in texts
    ]

    metadatas = [
        {
            "document_id": "search-test",
            "chunk_index": 0,
        },
        {
            "document_id": "search-test",
            "chunk_index": 1,
        },
        {
            "document_id": "search-test",
            "chunk_index": 2,
        },
    ]

    add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    query = "What is Python used for?"

    query_embedding = embed_text(query)

    results = search_chunks(
        query_embedding=query_embedding,
        n_results=3,
    )

    print("\nSearch results:")
    print(results["documents"])

    assert len(results["documents"][0]) == 3

    assert "Python" in results["documents"][0][0]