import logging

from app.core.logging import configure_logging
from app.workers.worker_config import create_document_worker


def main() -> None:
    configure_logging()

    logger = logging.getLogger(__name__)

    worker = create_document_worker()

    logger.info(
        "Starting document processing worker",
        extra={
            "event": "document_worker_starting",
        },
    )

    worker.work(
        burst=False,
        logging_level="INFO",
    )


if __name__ == "__main__":
    main()
