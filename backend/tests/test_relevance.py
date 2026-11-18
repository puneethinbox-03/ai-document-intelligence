from app.services.rag.relevance.relevance_service import (
    calculate_relevance,
)


def test_empty_chunks_return_low_relevance():
    result = calculate_relevance([])

    assert result.level == "low"
    assert result.score == 0.0
    assert result.evidence_count == 0
    assert result.top_rerank_score is None


def test_high_relevance():
    chunks = [
        type(
            "Chunk",
            (),
            {
                "score": 2.0,
            },
        )(),
        type(
            "Chunk",
            (),
            {
                "score": 1.5,
            },
        )(),
    ]

    result = calculate_relevance(chunks)

    assert result.level == "high"
    assert result.evidence_count == 2
    assert result.score > 0.70


def test_medium_or_low_relevance():
    chunks = [
        type(
            "Chunk",
            (),
            {
                "score": 0.0,
            },
        )(),
    ]

    result = calculate_relevance(chunks)

    assert result.level in {
        "medium",
        "low",
    }


def test_negative_score_is_handled():
    chunks = [
        type(
            "Chunk",
            (),
            {
                "score": -3.0,
            },
        )(),
    ]

    result = calculate_relevance(chunks)

    assert 0.0 <= result.score <= 1.0
    assert result.top_rerank_score == -3.0