from app.services.embeddings.embedding_service import embed_text
from app.services.vectorstore.chroma_service import search_chunks


def test_real_document_search():

    query = "What is discussed in this document?"

    query_embedding = embed_text(query)

    results = search_chunks(
        query_embedding=query_embedding,
        n_results=3,
    )

    print("\nSearch results:")
    print(results["documents"])

    assert len(results["documents"][0]) > 0