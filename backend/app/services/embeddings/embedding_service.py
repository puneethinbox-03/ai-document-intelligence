from typing import List

from .embedding_model import (
    get_embedding_model,
    NORMALIZE_EMBEDDINGS,
)


def embed_text(text: str) -> List[float]:
    """
    Generate an embedding vector for a single text.
    """

    model = get_embedding_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True
    )

    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embedding vectors for multiple texts.
    """

    if not texts:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True
    )

    return embeddings.tolist()