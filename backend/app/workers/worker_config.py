import logging
import os

from rq import SimpleWorker, Worker
from rq.serializers import JSONSerializer

from app.core.queue import create_document_processing_queue

logger = logging.getLogger(__name__)


def create_document_worker():
    """
    Create the appropriate RQ worker for the current platform.

    Windows uses SimpleWorker because the standard RQ worker
    relies on process-forking behaviour that is unsuitable
    for native Windows development.

    Linux uses the standard RQ Worker.
    """

    queue = create_document_processing_queue()

    if os.name == "nt":
        worker_class = SimpleWorker
        worker_mode = "simple"
    else:
        worker_class = Worker
        worker_mode = "standard"

    worker = worker_class(
        queues=[queue],
        connection=queue.connection,
        serializer=JSONSerializer,
        log_job_description=False,
    )

    logger.info(
        "Document processing worker configured",
        extra={
            "event": "document_worker_configured",
            "worker_mode": worker_mode,
            "queue_name": queue.name,
        },
    )

    return worker
