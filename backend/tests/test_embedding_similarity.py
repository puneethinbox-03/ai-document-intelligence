import numpy as np

from app.services.embeddings.embedding_service import embed_texts


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)

    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )


def test_semantic_similarity():
    texts = [
        "Python is a programming language.",
        "Python is commonly used for software development.",
        "The weather is sunny today.",
    ]

    embeddings = embed_texts(texts)

    related_similarity = cosine_similarity(
        embeddings[0],
        embeddings[1],
    )

    unrelated_similarity = cosine_similarity(
        embeddings[0],
        embeddings[2],
    )

    print("Related similarity:", related_similarity)
    print("Unrelated similarity:", unrelated_similarity)

    assert related_similarity > unrelated_similarity