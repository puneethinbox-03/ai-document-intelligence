from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import (
    add_chunks,
    search_chunks,
)


def test_similarity_ranking():

    texts = [
        "Python is a programming language used for software development.",
        "Python supports object oriented programming and scripting.",
        "SQL is used to query relational databases.",
        "Basketball is a popular sport played around the world.",
    ]

    embeddings = embed_texts(texts)

    chunk_ids = [
        "ranking-python-1",
        "ranking-python-2",
        "ranking-sql",
        "ranking-basketball",
    ]

    metadatas = [
        {"document_id": "ranking-test", "chunk_index": 0},
        {"document_id": "ranking-test", "chunk_index": 1},
        {"document_id": "ranking-test", "chunk_index": 2},
        {"document_id": "ranking-test", "chunk_index": 3},
    ]

    add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    query_embedding = embed_texts(
        ["What is Python programming?"]
    )[0]

    result = search_chunks(
        query_embedding=query_embedding,
        n_results=3,
    )

    print("\nRanking results:")
    print(result["documents"])
    print("\nDistances:")
    print(result["distances"])

    assert len(result["documents"][0]) == 3

    top_result = result["documents"][0][0]

    assert "Python" in top_result