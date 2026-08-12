from app.services.embeddings.embedding_service import embed_texts
from app.services.vectorstore.chroma_service import (
    add_chunks,
    search_chunks,
)


def test_metadata_filter():

    texts = [
        "Python is a programming language.",
        "SQL is used to query databases.",
        "Basketball is a popular sport.",
    ]

    embeddings = embed_texts(texts)

    chunk_ids = [
        "filter-python",
        "filter-sql",
        "filter-basketball",
    ]

    metadatas = [
        {
            "document_id": "document-a",
            "chunk_index": 0,
        },
        {
            "document_id": "document-a",
            "chunk_index": 1,
        },
        {
            "document_id": "document-b",
            "chunk_index": 0,
        },
    ]

    add_chunks(
        chunk_ids=chunk_ids,
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    query_embedding = embeddings[0]

    result = search_chunks(
        query_embedding=query_embedding,
        n_results=5,
        where={"document_id": "document-a"},
    )

    documents = result["documents"][0]

    print("\nFiltered results:")
    print(documents)

    assert len(documents) == 2