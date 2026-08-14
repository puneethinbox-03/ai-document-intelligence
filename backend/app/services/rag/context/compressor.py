import re

from app.services.rag.retrieval.models import RetrievedChunk


def _split_sentences(text: str) -> list[str]:
    """Split text into simple sentences."""
    if not text or not text.strip():
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase terms."""
    return set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text.lower(),
        )
    )


def _sentence_relevance(
    query_tokens: set[str],
    sentence: str,
) -> float:
    """Calculate simple lexical relevance between query and sentence."""
    if not query_tokens or not sentence:
        return 0.0

    sentence_tokens = _tokenize(sentence)

    if not sentence_tokens:
        return 0.0

    overlap = query_tokens.intersection(sentence_tokens)

    return len(overlap) / len(query_tokens)


def compress_context(
    query: str,
    chunks: list[RetrievedChunk],
    max_sentences_per_chunk: int = 3,
) -> list[RetrievedChunk]:
    """
    Compress retrieved chunks by keeping the most
    query-relevant sentences from each chunk.
    """

    if not query or not query.strip():
        return []

    if not chunks:
        return []

    if max_sentences_per_chunk <= 0:
        return []

    query_tokens = _tokenize(query)

    if not query_tokens:
        return []

    compressed_chunks: list[RetrievedChunk] = []

    for chunk in chunks:
        sentences = _split_sentences(chunk.text)

        if not sentences:
            continue

        ranked_sentences = sorted(
            enumerate(sentences),
            key=lambda item: (
                _sentence_relevance(
                    query_tokens,
                    item[1],
                ),
                -item[0],
            ),
            reverse=True,
        )

        selected = ranked_sentences[
            :max_sentences_per_chunk
        ]

        selected.sort(key=lambda item: item[0])

        compressed_text = " ".join(
            sentence
            for _, sentence in selected
        )

        if not compressed_text:
            continue

        compressed_chunks.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=compressed_text,
                metadata=chunk.metadata,
                score=chunk.score,
            )
        )

    return compressed_chunks