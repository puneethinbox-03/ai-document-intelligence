import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.processing_job import DocumentProcessingJob
from app.models.processing_outbox import DocumentProcessingOutbox
from app.services.queue_service import (
    DISPATCH_ACTIVE,
    DISPATCH_MISSING,
    DISPATCH_TERMINAL,
    DISPATCH_UNVERIFIED,
    enqueue_document_processing,
    verify_document_processing_dispatch,
)

logger = logging.getLogger(__name__)

OUTBOX_LEASE_SECONDS = 60
OUTBOX_RECONCILIATION_COOLDOWN_SECONDS = 60

OUTBOX_RETRY_BACKOFF_SECONDS = (
    30,
    120,
    300,
)

MAX_OUTBOX_BATCH_SIZE = 100


def _validate_batch_size(batch_size: int) -> None:
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not 1 <= batch_size <= MAX_OUTBOX_BATCH_SIZE
    ):
        raise ValueError(
            f"batch_size must be between 1 and {MAX_OUTBOX_BATCH_SIZE}"
        )


def _get_retry_delay(delivery_attempts: int) -> int:
    """
    Return a bounded retry delay.

    Delivery attempts are counted when a record is claimed.
    The delay increases and then remains capped at five minutes.
    """

    index = min(
        max(delivery_attempts - 1, 0),
        len(OUTBOX_RETRY_BACKOFF_SECONDS) - 1,
    )

    return OUTBOX_RETRY_BACKOFF_SECONDS[index]


def _claim_pending_outbox_records(
    session_factory: Callable[[], Session],
    *,
    batch_size: int,
) -> list[dict]:
    """
    Claim due outbox records using PostgreSQL row-level locks.

    The lease is committed before Redis delivery. If the process
    crashes, another dispatcher can reclaim the record after the
    lease expires and reuse its stable dispatch ID.
    """

    db = session_factory()

    try:
        now = datetime.now(timezone.utc)

        statement = (
            select(DocumentProcessingOutbox)
            .where(
                DocumentProcessingOutbox.dispatched_at.is_(None),
                DocumentProcessingOutbox.available_at <= now,
                or_(
                    DocumentProcessingOutbox.lease_expires_at.is_(None),
                    DocumentProcessingOutbox.lease_expires_at <= now,
                ),
            )
            .order_by(
                DocumentProcessingOutbox.available_at.asc(),
                DocumentProcessingOutbox.created_at.asc(),
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )

        records = db.scalars(statement).all()

        claimed_records = []

        for record in records:
            lease_token = uuid4()

            record.lease_token = lease_token
            record.lease_expires_at = (
                now + timedelta(seconds=OUTBOX_LEASE_SECONDS)
            )
            record.delivery_attempts += 1

            claimed_records.append(
                {
                    "outbox_id": record.id,
                    "processing_job_id": record.processing_job_id,
                    "dispatch_id": record.dispatch_id,
                    "lease_token": lease_token,
                    "delivery_attempts": record.delivery_attempts,
                }
            )

        db.commit()

        return claimed_records

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _mark_outbox_dispatched(
    session_factory: Callable[[], Session],
    *,
    outbox_id: UUID,
    lease_token: UUID,
) -> bool:
    """
    Mark delivery successful only if this dispatcher still owns
    the record's lease.
    """

    db = session_factory()

    try:
        statement = (
            update(DocumentProcessingOutbox)
            .where(
                DocumentProcessingOutbox.id == outbox_id,
                DocumentProcessingOutbox.lease_token == lease_token,
                DocumentProcessingOutbox.dispatched_at.is_(None),
            )
            .values(
                dispatched_at=datetime.now(timezone.utc),
                lease_expires_at=None,
                lease_token=None,
                last_error_code=None,
            )
        )

        result = db.execute(statement)
        db.commit()

        return result.rowcount == 1

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _schedule_outbox_delivery_retry(
    session_factory: Callable[[], Session],
    *,
    outbox_id: UUID,
    lease_token: UUID,
    delivery_attempts: int,
) -> bool:
    """
    Release a failed delivery and make it eligible after backoff.

    The record is never deleted because Redis is unavailable.
    Raw exception details are never stored in PostgreSQL.
    """

    db = session_factory()

    try:
        delay_seconds = _get_retry_delay(delivery_attempts)

        statement = (
            update(DocumentProcessingOutbox)
            .where(
                DocumentProcessingOutbox.id == outbox_id,
                DocumentProcessingOutbox.lease_token == lease_token,
                DocumentProcessingOutbox.dispatched_at.is_(None),
            )
            .values(
                lease_token=None,
                lease_expires_at=(
                    datetime.now(timezone.utc)
                    + timedelta(seconds=delay_seconds)
                ),
                last_error_code="QUEUE_UNAVAILABLE",
            )
        )

        result = db.execute(statement)
        db.commit()

        return result.rowcount == 1

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _claim_dispatched_outbox_records(
    session_factory: Callable[[], Session],
    *,
    batch_size: int,
) -> list[dict]:
    """
    Temporarily lease dispatched records whose PostgreSQL jobs
    are still queued.

    The database transaction ends before Redis is contacted.
    The existing lease fields also provide a reconciliation cooldown.
    """

    db = session_factory()

    try:
        now = datetime.now(timezone.utc)

        statement = (
            select(DocumentProcessingOutbox)
            .join(
                DocumentProcessingJob,
                DocumentProcessingJob.id
                == DocumentProcessingOutbox.processing_job_id,
            )
            .where(
                DocumentProcessingOutbox.dispatched_at.is_not(None),
                DocumentProcessingJob.status == "queued",
                or_(
                    DocumentProcessingOutbox.lease_expires_at.is_(None),
                    DocumentProcessingOutbox.lease_expires_at <= now,
                ),
            )
            .order_by(
                DocumentProcessingOutbox.dispatched_at.asc(),
                DocumentProcessingOutbox.created_at.asc(),
            )
            .limit(batch_size)
            .with_for_update(
                skip_locked=True,
                of=DocumentProcessingOutbox,
            )
        )

        records = db.scalars(statement).all()
        claimed_records = []

        for record in records:
            lease_token = uuid4()

            record.lease_token = lease_token
            record.lease_expires_at = (
                now
                + timedelta(
                    seconds=OUTBOX_RECONCILIATION_COOLDOWN_SECONDS
                )
            )

            claimed_records.append(
                {
                    "outbox_id": record.id,
                    "processing_job_id": record.processing_job_id,
                    "dispatch_id": record.dispatch_id,
                    "lease_token": lease_token,
                }
            )

        db.commit()
        return claimed_records

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _release_reconciliation_lease(
    session_factory: Callable[[], Session],
    *,
    outbox_id: UUID,
    lease_token: UUID,
) -> bool:
    """
    Release a reconciliation lease while retaining a cooldown.

    The record remains dispatched and is not sent to Redis again.
    """

    db = session_factory()

    try:
        now = datetime.now(timezone.utc)

        statement = (
            update(DocumentProcessingOutbox)
            .where(
                DocumentProcessingOutbox.id == outbox_id,
                DocumentProcessingOutbox.lease_token == lease_token,
                DocumentProcessingOutbox.dispatched_at.is_not(None),
            )
            .values(
                lease_token=None,
                lease_expires_at=(
                    now
                    + timedelta(
                        seconds=OUTBOX_RECONCILIATION_COOLDOWN_SECONDS
                    )
                ),
            )
        )

        result = db.execute(statement)
        db.commit()

        return result.rowcount == 1

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _reopen_dispatched_outbox_record(
    session_factory: Callable[[], Session],
    *,
    outbox_id: UUID,
    lease_token: UUID,
) -> bool:
    """
    Reopen a dispatched record only if its PostgreSQL job is
    still queued and this reconciliation process owns the lease.

    The original dispatch ID is retained for safe redelivery.
    """

    db = session_factory()

    try:
        now = datetime.now(timezone.utc)

        queued_job_exists = exists(
            select(DocumentProcessingJob.id).where(
                DocumentProcessingJob.id
                == DocumentProcessingOutbox.processing_job_id,
                DocumentProcessingJob.status == "queued",
            )
        )

        statement = (
            update(DocumentProcessingOutbox)
            .where(
                DocumentProcessingOutbox.id == outbox_id,
                DocumentProcessingOutbox.lease_token == lease_token,
                DocumentProcessingOutbox.dispatched_at.is_not(None),
                queued_job_exists,
            )
            .values(
                dispatched_at=None,
                available_at=now,
                lease_expires_at=None,
                lease_token=None,
                last_error_code="REDIS_JOB_NOT_ACTIVE",
            )
        )

        result = db.execute(statement)
        db.commit()

        return result.rowcount == 1

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def reconcile_dispatched_document_jobs(
    *,
    batch_size: int = 10,
    session_factory: Callable[[], Session] | None = None,
    verify_func: Callable[[UUID, UUID], str] | None = None,
) -> dict[str, int]:
    """
    Recover PostgreSQL jobs that remain queued after Redis loses
    their previously dispatched RQ jobs.

    Only confirmed missing or terminal Redis jobs are reopened.
    Active and unverifiable Redis jobs remain dispatched.

    Redis verification happens outside PostgreSQL transactions.
    Only processing-job and dispatch UUIDs are passed to Redis.
    """

    _validate_batch_size(batch_size)

    session_factory = session_factory or SessionLocal
    verify_func = (
        verify_func or verify_document_processing_dispatch
    )

    claimed_records = _claim_dispatched_outbox_records(
        session_factory,
        batch_size=batch_size,
    )

    result = {
        "claimed": len(claimed_records),
        "reopened": 0,
        "active": 0,
        "unverified": 0,
        "stale": 0,
    }

    for record in claimed_records:
        try:
            dispatch_status = verify_func(
                record["processing_job_id"],
                record["dispatch_id"],
            )
        except Exception:
            logger.error(
                "Document processing dispatch verification failed",
                extra={
                    "event": "document_dispatch_verification_failed",
                },
            )
            dispatch_status = DISPATCH_UNVERIFIED

        if dispatch_status in (
            DISPATCH_MISSING,
            DISPATCH_TERMINAL,
        ):
            reopened = _reopen_dispatched_outbox_record(
                session_factory,
                outbox_id=record["outbox_id"],
                lease_token=record["lease_token"],
            )

            if reopened:
                result["reopened"] += 1

                logger.warning(
                    "Inactive Redis dispatch reopened for delivery",
                    extra={
                        "event": "document_dispatch_reopened",
                    },
                )
            else:
                result["stale"] += 1

                # If the PostgreSQL job is no longer queued, retain
                # the dispatched record and apply the cooldown.
                _release_reconciliation_lease(
                    session_factory,
                    outbox_id=record["outbox_id"],
                    lease_token=record["lease_token"],
                )

        elif dispatch_status == DISPATCH_ACTIVE:
            released = _release_reconciliation_lease(
                session_factory,
                outbox_id=record["outbox_id"],
                lease_token=record["lease_token"],
            )

            if released:
                result["active"] += 1
            else:
                result["stale"] += 1

        else:
            # Unknown or unverified states must never trigger
            # automatic redelivery.
            released = _release_reconciliation_lease(
                session_factory,
                outbox_id=record["outbox_id"],
                lease_token=record["lease_token"],
            )

            if released:
                result["unverified"] += 1
            else:
                result["stale"] += 1

    return result


def dispatch_pending_document_jobs(
    *,
    batch_size: int = 10,
    session_factory: Callable[[], Session] | None = None,
    enqueue_func: Callable | None = None,
) -> dict[str, int]:
    """
    Deliver pending PostgreSQL outbox records to Redis.

    PostgreSQL remains the source of truth. Redis receives only:
    - The processing-job UUID as the worker argument.
    - The stable dispatch UUID as the RQ job ID.

    Delivery is at-least-once. Stable dispatch IDs and atomic
    database job claiming protect against duplicate execution.

    Returns counts for claimed, dispatched, failed and stale records.
    """

    _validate_batch_size(batch_size)

    session_factory = session_factory or SessionLocal
    enqueue_func = enqueue_func or enqueue_document_processing

    claimed_records = _claim_pending_outbox_records(
        session_factory,
        batch_size=batch_size,
    )

    result = {
        "claimed": len(claimed_records),
        "dispatched": 0,
        "failed": 0,
        "stale": 0,
    }

    for record in claimed_records:
        try:
            enqueue_func(
                record["processing_job_id"],
                dispatch_id=record["dispatch_id"],
            )

        except Exception:
            logger.error(
                "Document processing outbox delivery failed",
                extra={
                    "event": "document_outbox_delivery_failed",
                },
            )

            released = _schedule_outbox_delivery_retry(
                session_factory,
                outbox_id=record["outbox_id"],
                lease_token=record["lease_token"],
                delivery_attempts=record["delivery_attempts"],
            )

            if released:
                result["failed"] += 1
            else:
                result["stale"] += 1

            continue

        marked = _mark_outbox_dispatched(
            session_factory,
            outbox_id=record["outbox_id"],
            lease_token=record["lease_token"],
        )

        if marked:
            result["dispatched"] += 1

            logger.info(
                "Document processing outbox record dispatched",
                extra={
                    "event": "document_outbox_dispatched",
                },
            )
        else:
            result["stale"] += 1

            logger.warning(
                "Document processing outbox lease was no longer owned",
                extra={
                    "event": "document_outbox_lease_lost",
                },
            )

    return result
