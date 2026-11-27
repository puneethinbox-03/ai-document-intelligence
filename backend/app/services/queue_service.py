
import logging
from uuid import UUID, uuid4

from rq.exceptions import DuplicateJobError, NoSuchJobError
from rq.job import Job, JobStatus
from rq.serializers import JSONSerializer

from app.core.queue import (
    DOCUMENT_PROCESSING_JOB_TIMEOUT_SECONDS,
    create_document_processing_queue,
)

logger = logging.getLogger(__name__)

DOCUMENT_PROCESSING_FUNCTION = (
    "app.workers.document_worker.process_document_job"
)

ACCEPTED_DUPLICATE_STATUSES = {
    JobStatus.CREATED,
    JobStatus.QUEUED,
    JobStatus.STARTED,
    JobStatus.DEFERRED,
    JobStatus.SCHEDULED,
    JobStatus.RATE_LIMITED,
    JobStatus.READY_TO_ENQUEUE,
}

TERMINAL_DUPLICATE_STATUSES = {
    JobStatus.FINISHED,
    JobStatus.FAILED,
    JobStatus.STOPPED,
    JobStatus.CANCELED,
}

DISPATCH_ACTIVE = "active"
DISPATCH_MISSING = "missing"
DISPATCH_TERMINAL = "terminal"
DISPATCH_UNVERIFIED = "unverified"


class QueueEnqueueError(RuntimeError):
    """Safe error raised when a background job cannot be queued."""


def verify_document_processing_dispatch(
    processing_job_id: UUID,
    dispatch_id: UUID,
) -> str:
    """
    Read-only verification of a previously dispatched RQ job.

    Returns active, missing, terminal, or unverified.

    This function never enqueues, deletes, or modifies Redis jobs.
    """

    if not isinstance(processing_job_id, UUID):
        raise TypeError("processing_job_id must be a UUID")

    if not isinstance(dispatch_id, UUID):
        raise TypeError("dispatch_id must be a UUID")

    try:
        queue = create_document_processing_queue()

        try:
            existing_job = Job.fetch(
                str(dispatch_id),
                connection=queue.connection,
                serializer=JSONSerializer,
            )
        except NoSuchJobError:
            return DISPATCH_MISSING

        payload_matches = (
            existing_job.func_name == DOCUMENT_PROCESSING_FUNCTION
            and existing_job.args == (str(processing_job_id),)
            and existing_job.kwargs == {}
        )

        if not payload_matches:
            logger.error(
                "Redis dispatch payload verification failed",
                extra={"event": "document_job_dispatch_mismatch"},
            )
            return DISPATCH_UNVERIFIED

        existing_status = existing_job.get_status(refresh=True)

        if existing_status in ACCEPTED_DUPLICATE_STATUSES:
            return DISPATCH_ACTIVE

        if existing_status in TERMINAL_DUPLICATE_STATUSES:
            return DISPATCH_TERMINAL

        logger.warning(
            "Redis dispatch has an unsupported status",
            extra={"event": "document_job_dispatch_status_unverified"},
        )
        return DISPATCH_UNVERIFIED

    except Exception:
        logger.error(
            "Redis dispatch verification failed",
            extra={"event": "document_job_verification_failed"},
        )
        return DISPATCH_UNVERIFIED


def enqueue_document_processing(
    processing_job_id: UUID,
    dispatch_id: UUID | None = None,
) -> Job:
    """
    Enqueue one document-processing delivery.

    Redis receives only the PostgreSQL processing-job UUID.
    The stable outbox dispatch UUID is used as the RQ job ID.

    Duplicate delivery is accepted only after verifying the existing
    job's function, arguments, keyword arguments, and status.
    """

    if not isinstance(processing_job_id, UUID):
        raise TypeError("processing_job_id must be a UUID")

    if dispatch_id is None:
        dispatch_id = uuid4()
    elif not isinstance(dispatch_id, UUID):
        raise TypeError("dispatch_id must be a UUID")

    try:
        queue = create_document_processing_queue()

        enqueue_kwargs = {
            "job_id": str(dispatch_id),
            "unique": True,
            "job_timeout": DOCUMENT_PROCESSING_JOB_TIMEOUT_SECONDS,
        }

        try:
            return queue.enqueue(
                DOCUMENT_PROCESSING_FUNCTION,
                str(processing_job_id),
                **enqueue_kwargs,
            )

        except DuplicateJobError:
            existing_job = Job.fetch(
                str(dispatch_id),
                connection=queue.connection,
                serializer=JSONSerializer,
            )

            payload_matches = (
                existing_job.func_name == DOCUMENT_PROCESSING_FUNCTION
                and existing_job.args == (str(processing_job_id),)
                and existing_job.kwargs == {}
            )

            if not payload_matches:
                logger.error(
                    "Existing Redis dispatch does not match its outbox record",
                    extra={"event": "document_job_dispatch_mismatch"},
                )
                raise QueueEnqueueError(
                    "Document processing dispatch could not be verified"
                ) from None

            existing_status = existing_job.get_status(refresh=True)

            if existing_status in ACCEPTED_DUPLICATE_STATUSES:
                logger.info(
                    "Document processing dispatch was already accepted",
                    extra={
                        "event": "document_job_duplicate_verified",
                        "redis_job_status": existing_status.value,
                    },
                )
                return existing_job

            if existing_status in TERMINAL_DUPLICATE_STATUSES:
                logger.warning(
                    "Removing terminal Redis job before retrying delivery",
                    extra={
                        "event": "document_job_terminal_duplicate_replaced",
                        "redis_job_status": existing_status.value,
                    },
                )

                existing_job.delete()

                return queue.enqueue(
                    DOCUMENT_PROCESSING_FUNCTION,
                    str(processing_job_id),
                    **enqueue_kwargs,
                )

            logger.error(
                "Existing Redis dispatch has an unsupported status",
                extra={"event": "document_job_dispatch_status_rejected"},
            )
            raise QueueEnqueueError(
                "Document processing dispatch could not be verified"
            ) from None

    except QueueEnqueueError:
        raise

    except Exception:
        logger.error(
            "Document processing job could not be enqueued",
            extra={"event": "document_job_enqueue_failed"},
        )
        raise QueueEnqueueError(
            "Document processing could not be scheduled"
        ) from None
