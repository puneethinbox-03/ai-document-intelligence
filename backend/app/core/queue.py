from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

from app.core.redis_client import create_redis_client


DOCUMENT_PROCESSING_QUEUE_NAME = "document_processing"
DOCUMENT_PROCESSING_JOB_TIMEOUT_SECONDS = 900


def create_document_processing_queue(
    connection: Redis | None = None,
) -> Queue:
    """
    Create the document-processing queue.

    Queue payloads must contain identifiers only.
    Never enqueue document text, file contents, credentials,
    session tokens, or other sensitive information.
    """
    redis_connection = connection or create_redis_client()

    return Queue(
        name=DOCUMENT_PROCESSING_QUEUE_NAME,
        connection=redis_connection,
        default_timeout=DOCUMENT_PROCESSING_JOB_TIMEOUT_SECONDS,
        serializer=JSONSerializer,
        is_async=True,
    )
