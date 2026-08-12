from sentence_transformers import SentenceTransformer


MODEL_NAME = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMENSION = 1024
NORMALIZE_EMBEDDINGS = True

_model = None


def get_embedding_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model