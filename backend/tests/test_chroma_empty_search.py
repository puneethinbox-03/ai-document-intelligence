from app.services.vectorstore.chroma_service import search_chunks


def test_empty_search():

    result = search_chunks([])

    assert result["ids"] == [[]]
    assert result["documents"] == [[]]
    assert result["metadatas"] == [[]]
    assert result["distances"] == [[]]