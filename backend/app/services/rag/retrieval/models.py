from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RetrievedChunk:
    """
    Represents a document chunk returned by a RAG retriever.
    """

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: Optional[float] = None