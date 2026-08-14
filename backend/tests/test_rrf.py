from app.services.rag.fusion.rrf import reciprocal_rank_fusion
from app.services.rag.retrieval.models import RetrievedChunk


def make_chunk(
    chunk_id: str,
    text: str,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        metadata={},
    )


def test_rrf_combines_multiple_result_lists():
    vector_results = [
        make_chunk("chunk-a", "Python programming"),
        make_chunk("chunk-b", "SQL databases"),
        make_chunk("chunk-c", "Machine learning"),
    ]

    keyword_results = [
        make_chunk("chunk-b", "SQL databases"),
        make_chunk("chunk-a", "Python programming"),
        make_chunk("chunk-d", "Basketball"),
    ]

    results = reciprocal_rank_fusion(
        result_lists=[
            vector_results,
            keyword_results,
        ],
        k=60,
        n_results=4,
    )

    assert len(results) == 4

    result_ids = [result.chunk_id for result in results]

    assert "chunk-a" in result_ids
    assert "chunk-b" in result_ids
    assert "chunk-c" in result_ids
    assert "chunk-d" in result_ids


def test_rrf_rewards_documents_present_in_multiple_lists():
    vector_results = [
        make_chunk("chunk-a", "Python"),
        make_chunk("chunk-b", "SQL"),
    ]

    keyword_results = [
        make_chunk("chunk-b", "SQL"),
        make_chunk("chunk-a", "Python"),
    ]

    results = reciprocal_rank_fusion(
        result_lists=[
            vector_results,
            keyword_results,
        ],
        k=60,
        n_results=2,
    )

    assert len(results) == 2

    result_ids = [result.chunk_id for result in results]

    # Both appear in both lists.
    assert set(result_ids) == {"chunk-a", "chunk-b"}


def test_rrf_duplicate_chunk_is_merged():
    vector_results = [
        make_chunk("chunk-a", "Python"),
    ]

    keyword_results = [
        make_chunk("chunk-a", "Python"),
    ]

    results = reciprocal_rank_fusion(
        result_lists=[
            vector_results,
            keyword_results,
        ],
        k=60,
        n_results=5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-a"


def test_rrf_respects_n_results():
    results = reciprocal_rank_fusion(
        result_lists=[
            [
                make_chunk("chunk-a", "A"),
                make_chunk("chunk-b", "B"),
                make_chunk("chunk-c", "C"),
            ]
        ],
        k=60,
        n_results=2,
    )

    assert len(results) == 2


def test_rrf_empty_results():
    results = reciprocal_rank_fusion(
        result_lists=[],
        k=60,
        n_results=5,
    )

    assert results == []


def test_rrf_invalid_k():
    try:
        reciprocal_rank_fusion(
            result_lists=[],
            k=0,
            n_results=5,
        )
        assert False
    except ValueError:
        assert True