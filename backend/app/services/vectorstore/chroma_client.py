from pathlib import Path

import chromadb


CHROMA_PATH = Path("data/chroma")

_client = None


def get_chroma_client():
    global _client

    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_PATH)
        )

    return _client