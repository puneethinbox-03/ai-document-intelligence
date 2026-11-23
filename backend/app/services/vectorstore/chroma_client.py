
import chromadb

from app.core.config import settings


# ============================================================
# Configuration
# ============================================================

# Use the centralized ChromaDB storage path.
CHROMA_PATH = settings.chroma_path


# ============================================================
# ChromaDB Client
# ============================================================

_client = None


def get_chroma_client():
    """
    Return the reusable persistent ChromaDB client.

    The client is initialized only once and reused
    throughout the application's lifetime.
    """

    global _client

    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_PATH)
        )

    return _client
