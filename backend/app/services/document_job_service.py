from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.processing_job import DocumentProcessingJob
from app.models.processing_outbox import DocumentProcessingOutbox
from app.models.user import User

VALID_JOB_STATUSES = {
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
}

ALLOWED_STATUS_TRANSITIONS = {
    "queued": {"processing", "failed", "cancelled"},
    "processing": {"queued", "completed", "failed", "cancelled"},
    "failed": {"queued", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

SAFE_JOB_ERRORS = {
    "DOCUMENT_UNAVAILABLE": "Document is unavailable for processing",
    "PROCESSING_FAILED": "Document processing failed",
    "SENSITIVE_DATA_SCAN_FAILED": "Document security validation failed",
    "SANITIZATION_FAILED": "Document sanitization failed",
    "INDEXING_FAILED": "Document indexing failed",
    "QUEUE_UNAVAILABLE": "Background processing is temporarily unavailable",
}
RETRYABLE_JOB_ERRORS = {
    "PROCESSING_FAILED",
    "INDEXING_FAILED",
}

RETRY_BACKOFF_SECONDS = {
    1: 30,
    2: 120,
}

def create_document_processing_job(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
    max_attempts: int = 3,
) -> DocumentProcessingJob | None:
    """
    Create a queued processing job for an owner's document.

    The document is locked while checking for an existing active job.
    If a queued or processing job already exists, return it.

    Returns None when the document does not belong to the owner.
    """

    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts < 1
        or max_attempts > 10
    ):
        raise ValueError("max_attempts must be between 1 and 10")

    try:
        document_statement = (
            select(Document)
            .where(
                Document.id == document_id,
                Document.user_id == owner_id,
            )
            .with_for_update()
        )

        document = db.scalar(document_statement)

        if document is None:
            return None

        if document.status not in {"uploaded", "queued"}:
            raise ValueError(
                "Document is not eligible for processing"
            )

        active_job_statement = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.document_id == document_id,
                DocumentProcessingJob.status.in_(
                    ["queued", "processing"]
                ),
            )
            .order_by(DocumentProcessingJob.created_at.desc())
        )

        existing_job = db.scalar(active_job_statement)

        if existing_job is not None:
            # Release the document row lock before returning.
            db.commit()
            return existing_job

        job = DocumentProcessingJob(
            document_id=document.id,
            status="queued",
            attempts=0,
            max_attempts=max_attempts,
            available_at=datetime.now(timezone.utc),
        )

        document.status = "queued"
        document.error_code = None
        document.error_message = None

        db.add(job)
        db.flush()

        outbox_record = DocumentProcessingOutbox(
            processing_job_id=job.id,
            dispatch_id=uuid4(),
            available_at=job.available_at,
        )

        db.add(outbox_record)
        db.commit()

        return job

    except Exception:
        db.rollback()
        raise


def create_owned_document_with_processing_job(
    db: Session,
    *,
    owner_id: UUID,
    original_filename: str,
    storage_key: str,
    content_type: str,
    file_size_bytes: int,
    sha256_hash: str | None = None,
    max_attempts: int = 3,
) -> tuple[Document, DocumentProcessingJob]:
    """
    Create an owned document and its processing job atomically.

    Both database records are committed in one transaction.
    If either operation fails, both are rolled back.

    The original document remains in private storage.
    Only the processing-job UUID will subsequently be sent to Redis.
    """

    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or max_attempts < 1
        or max_attempts > 10
    ):
        raise ValueError("max_attempts must be between 1 and 10")

    try:
        document = Document(
            user_id=owner_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            sha256_hash=sha256_hash,
            status="queued",
        )

        db.add(document)
        db.flush()

        processing_job = DocumentProcessingJob(
            document_id=document.id,
            status="queued",
            attempts=0,
            max_attempts=max_attempts,
            available_at=datetime.now(timezone.utc),
        )

        db.add(processing_job)
        db.flush()

        outbox_record = DocumentProcessingOutbox(
            processing_job_id=processing_job.id,
            dispatch_id=uuid4(),
            available_at=processing_job.available_at,
        )

        db.add(outbox_record)
        db.commit()

        return document, processing_job

    except Exception:
        db.rollback()
        raise

def get_processing_job(
    db: Session,
    *,
    processing_job_id: UUID,
) -> DocumentProcessingJob | None:
    """Retrieve a processing job by its identifier."""

    return db.scalar(
        select(DocumentProcessingJob).where(
            DocumentProcessingJob.id == processing_job_id
        )
    )


def get_owned_processing_job(
    db: Session,
    *,
    processing_job_id: UUID,
    owner_id: UUID,
) -> DocumentProcessingJob | None:
    """
    Retrieve a processing job only when its document belongs
    to the specified owner.

    Missing and unowned jobs both return None.
    """

    statement = (
        select(DocumentProcessingJob)
        .join(
            Document,
            Document.id == DocumentProcessingJob.document_id,
        )
        .where(
            DocumentProcessingJob.id == processing_job_id,
            Document.user_id == owner_id,
        )
    )

    return db.scalar(statement)


def list_owned_processing_jobs(
    db: Session,
    *,
    document_id: UUID,
    owner_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[DocumentProcessingJob]:
    """
    List processing jobs for a document owned by the specified user.
    """

    if skip < 0:
        raise ValueError("skip cannot be negative")

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    statement = (
        select(DocumentProcessingJob)
        .join(
            Document,
            Document.id == DocumentProcessingJob.document_id,
        )
        .where(
            DocumentProcessingJob.document_id == document_id,
            Document.user_id == owner_id,
        )
        .order_by(DocumentProcessingJob.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def update_processing_job_status(
    db: Session,
    *,
    processing_job_id: UUID,
    status: str,
    error_code: str | None = None,
) -> DocumentProcessingJob | None:
    """
    Update a processing job using an explicit status transition.

    Attempts increase only when a job enters processing.

    When a job transitions back to queued:
    - Lock and update the associated document.
    - Create a transactional outbox record.
    - Commit all changes together.

    Error details are selected from a predefined allowlist.
    Raw exception messages must never be stored here.

    Returns None when the job or required document does not exist.
    """

    if status not in VALID_JOB_STATUSES:
        raise ValueError("Invalid processing job status")

    if error_code is not None and error_code not in SAFE_JOB_ERRORS:
        raise ValueError("Invalid processing job error code")

    if status == "failed" and error_code is None:
        raise ValueError("A safe error code is required for failed jobs")

    if status != "failed" and error_code is not None:
        raise ValueError(
            "Error codes are only permitted for failed jobs"
        )

    try:
        statement = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.id == processing_job_id
            )
            .with_for_update()
        )

        job = db.scalar(statement)

        if job is None:
            return None

        if status not in ALLOWED_STATUS_TRANSITIONS[job.status]:
            raise ValueError("Invalid processing job status transition")

        now = datetime.now(timezone.utc)

        if status == "processing":
            if job.attempts >= job.max_attempts:
                raise ValueError(
                    "Processing job has reached its attempt limit"
                )

            job.attempts += 1
            job.started_at = now
            job.completed_at = None
            job.error_code = None
            job.error_message = None

        elif status == "queued":
            if job.attempts >= job.max_attempts:
                raise ValueError(
                    "Processing job has reached its attempt limit"
                )

            document_statement = (
                select(Document)
                .where(
                    Document.id == job.document_id,
                )
                .with_for_update()
            )

            document = db.scalar(document_statement)

            if document is None:
                db.rollback()
                return None

            if document.status != job.status:
                raise ValueError(
                    "Document status does not match processing job status"
                )

            job.available_at = now
            job.started_at = None
            job.completed_at = None
            job.error_code = None
            job.error_message = None

            document.status = "queued"
            document.error_code = None
            document.error_message = None

            outbox_record = DocumentProcessingOutbox(
                processing_job_id=job.id,
                dispatch_id=uuid4(),
                available_at=job.available_at,
            )

            db.add(outbox_record)

        elif status in {"completed", "failed", "cancelled"}:
            job.completed_at = now

            if status == "failed":
                job.error_code = error_code
                job.error_message = SAFE_JOB_ERRORS[error_code]
            else:
                job.error_code = None
                job.error_message = None

        job.status = status

        db.commit()

        return job

    except Exception:
        db.rollback()
        raise

def claim_document_processing_job(
    db: Session,
    *,
    processing_job_id: UUID,
) -> DocumentProcessingJob | None:
    """
    Atomically claim a queued document-processing job.

    PostgreSQL row locks prevent concurrent workers from claiming
    the same job.

    The job and document statuses are updated in one transaction.

    Returns None when the job is missing, unavailable, already claimed,
    not ready, or cannot safely be processed.
    """

    try:
        now = datetime.now(timezone.utc)

        job_statement = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.id == processing_job_id,
                DocumentProcessingJob.status == "queued",
                DocumentProcessingJob.available_at <= now,
                DocumentProcessingJob.attempts
                < DocumentProcessingJob.max_attempts,
            )
            .with_for_update(skip_locked=True)
        )

        job = db.scalar(job_statement)

        if job is None:
            db.rollback()
            return None

        document_statement = (
            select(Document)
            .where(
                Document.id == job.document_id,
                Document.status.in_(["uploaded", "queued"]),
            )
            .with_for_update()
        )

        document = db.scalar(document_statement)

        if document is None:
            db.rollback()
            return None

        owner_statement = (
            select(User)
            .where(
                User.id == document.user_id,
                User.is_active.is_(True),
            )
        )

        owner = db.scalar(owner_statement)

        if owner is None:
            db.rollback()
            return None

        job.status = "processing"
        job.attempts += 1
        job.started_at = now
        job.completed_at = None
        job.error_code = None
        job.error_message = None

        document.status = "processing"
        document.error_code = None
        document.error_message = None

        db.commit()

        return job

    except Exception:
        db.rollback()
        raise

def schedule_document_processing_retry(
    db: Session,
    *,
    processing_job_id: UUID,
) -> DocumentProcessingJob | None:
    """
    Schedule an eligible failed job for a delayed retry.

    The job and document are locked and updated in one transaction.

    Only explicitly retryable errors are eligible.
    The attempt count is not incremented here; it increases
    when a worker successfully claims the job.

    Returns None when the job is missing, not failed, not retryable,
    exhausted, or its document is unavailable.
    """

    try:
        job_statement = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.id == processing_job_id,
                DocumentProcessingJob.status == "failed",
            )
            .with_for_update()
        )

        job = db.scalar(job_statement)

        if job is None:
            db.rollback()
            return None

        if job.error_code not in RETRYABLE_JOB_ERRORS:
            db.rollback()
            return None

        if job.attempts >= job.max_attempts:
            db.rollback()
            return None

        delay_seconds = RETRY_BACKOFF_SECONDS.get(job.attempts)

        if delay_seconds is None:
            db.rollback()
            return None

        document_statement = (
            select(Document)
            .where(
                Document.id == job.document_id,
                Document.status.in_(["processing", "failed"]),
            )
            .with_for_update()
        )

        document = db.scalar(document_statement)

        if document is None:
            db.rollback()
            return None

        now = datetime.now(timezone.utc)

        job.status = "queued"
        job.available_at = now + timedelta(
            seconds=delay_seconds
        )
        job.started_at = None
        job.completed_at = None
        job.error_code = None
        job.error_message = None

        document.status = "queued"
        document.error_code = None
        document.error_message = None

        outbox_record = DocumentProcessingOutbox(
            processing_job_id=job.id,
            dispatch_id=uuid4(),
            available_at=job.available_at,
        )

        db.add(outbox_record)
        db.commit()

        return job

    except Exception:
        db.rollback()
        raise
