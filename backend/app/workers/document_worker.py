
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class DocumentWorkerError(RuntimeError):
    """Safe exception for document worker failures."""


def process_document_job(processing_job_id: str) -> dict[str, str]:
    """
    Safely defer document processing until the secure processor exists.

    Phase 5 establishes queue and worker infrastructure only.

    The actual processor will be introduced in Phase 6. Until then:
    - Do not claim the PostgreSQL processing job.
    - Do not load the original document.
    - Do not read or extract document content.
    - Do not access embeddings, ChromaDB, BM25, or an LLM.
    - Leave the PostgreSQL job queued for later reconciliation.
    """

    try:
        job_id = UUID(processing_job_id)
    except (ValueError, TypeError, AttributeError):
        raise DocumentWorkerError(
            "Invalid document-processing job identifier"
        ) from None

    logger.warning(
        "Document processing deferred because the secure processor "
        "is not configured",
        extra={
            "event": "document_job_deferred",
            "processing_job_id": str(job_id),
        },
    )

    return {
        "status": "deferred",
        "reason": "secure_processor_not_configured",
        "processing_job_id": str(job_id),
    }
