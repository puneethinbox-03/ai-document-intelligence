
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

import app.models  # Register all SQLAlchemy models.

from app.core.database import SessionLocal
from app.models import (
    Document,
    DocumentProcessingJob,
    DocumentProcessingOutbox,
    User,
)
from app.services.document_job_service import (
    claim_document_processing_job,
    create_document_processing_job,
    get_owned_processing_job,
    list_owned_processing_jobs,
    schedule_document_processing_retry,
    update_processing_job_status,
)


@pytest.fixture
def postgres_document():
    """
    Create an isolated user and document in PostgreSQL.

    Only records created by this fixture are removed afterward.
    """

    db: Session = SessionLocal()

    owner_id = None
    document_id = uuid.uuid4()

    unique_value = uuid.uuid4().hex
    email = f"job-integration-{unique_value}@example.test"

    try:
        user = User(
            email=email,
            email_normalized=email,
            password_hash="integration-test-placeholder",
            display_name="Integration Test User",
        )

        db.add(user)
        db.flush()

        owner_id = user.id

        document = Document(
            id=document_id,
            user_id=owner_id,
            original_filename="integration-test.pdf",
            storage_key=f"integration-tests/{unique_value}.pdf",
            content_type="application/pdf",
            file_size_bytes=100,
            status="uploaded",
        )

        db.add(document)
        db.commit()

        yield {
            "db": db,
            "owner_id": owner_id,
            "document_id": document_id,
        }

    finally:
        db.rollback()

        if owner_id is not None:
            try:
                db.execute(
                    delete(DocumentProcessingJob).where(
                        DocumentProcessingJob.document_id
                        == document_id
                    )
                )

                db.execute(
                    delete(Document).where(
                        Document.id == document_id,
                        Document.user_id == owner_id,
                    )
                )

                db.execute(
                    delete(User).where(User.id == owner_id)
                )

                db.commit()

            except Exception:
                db.rollback()
                raise

        db.close()


def create_test_job(postgres_document):
    """Create a queued job for the fixture's document."""

    db = postgres_document["db"]

    return create_document_processing_job(
        db,
        document_id=postgres_document["document_id"],
        owner_id=postgres_document["owner_id"],
    )


@pytest.mark.integration
def test_postgres_creates_and_persists_processing_job(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]
    document_id = postgres_document["document_id"]

    job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert job is not None
    assert job.status == "queued"
    assert job.attempts == 0
    assert job.max_attempts == 3

    persisted_job = db.scalar(
        select(DocumentProcessingJob).where(
            DocumentProcessingJob.id == job.id
        )
    )

    assert persisted_job is not None
    assert persisted_job.document_id == document_id
    assert persisted_job.status == "queued"

    document = db.get(Document, document_id)

    assert document.status == "queued"


@pytest.mark.integration
def test_postgres_prevents_duplicate_active_jobs(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]
    document_id = postgres_document["document_id"]

    first_job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    second_job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert first_job.id == second_job.id

    job_count = db.scalar(
        select(func.count())
        .select_from(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.document_id == document_id,
            DocumentProcessingJob.status.in_(
                ["queued", "processing"]
            ),
        )
    )

    assert job_count == 1


@pytest.mark.integration
def test_postgres_enforces_processing_job_ownership(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]
    document_id = postgres_document["document_id"]

    job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    owned_job = get_owned_processing_job(
        db,
        processing_job_id=job.id,
        owner_id=owner_id,
    )

    unauthorized_job = get_owned_processing_job(
        db,
        processing_job_id=job.id,
        owner_id=uuid.uuid4(),
    )

    listed_jobs = list_owned_processing_jobs(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert owned_job is not None
    assert owned_job.id == job.id

    assert unauthorized_job is None

    assert len(listed_jobs) == 1
    assert listed_jobs[0].id == job.id


@pytest.mark.integration
def test_postgres_processing_job_lifecycle(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]
    document_id = postgres_document["document_id"]

    job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    processing_job = update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="processing",
    )

    assert processing_job.status == "processing"
    assert processing_job.attempts == 1
    assert processing_job.started_at is not None

    completed_job = update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="completed",
    )

    assert completed_job.status == "completed"
    assert completed_job.completed_at is not None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "completed"
    assert persisted_job.attempts == 1


@pytest.mark.integration
def test_postgres_processing_job_safe_failure(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]
    document_id = postgres_document["document_id"]

    job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="processing",
    )

    failed_job = update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="failed",
        error_code="PROCESSING_FAILED",
    )

    assert failed_job.status == "failed"
    assert failed_job.error_code == "PROCESSING_FAILED"
    assert failed_job.error_message == (
        "Document processing failed"
    )

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "failed"
    assert persisted_job.completed_at is not None


@pytest.mark.integration
def test_postgres_atomically_claims_queued_job(
    postgres_document,
):
    db = postgres_document["db"]
    document_id = postgres_document["document_id"]

    job = create_test_job(postgres_document)

    claimed_job = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert claimed_job is not None
    assert claimed_job.id == job.id
    assert claimed_job.status == "processing"
    assert claimed_job.attempts == 1
    assert claimed_job.started_at is not None

    document = db.get(Document, document_id)

    assert document.status == "processing"

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "processing"
    assert persisted_job.attempts == 1


@pytest.mark.integration
def test_postgres_rejects_second_claim_of_same_job(
    postgres_document,
):
    db = postgres_document["db"]

    job = create_test_job(postgres_document)

    first_claim = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    second_claim = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert first_claim is not None
    assert first_claim.status == "processing"
    assert second_claim is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "processing"
    assert persisted_job.attempts == 1


@pytest.mark.integration
def test_postgres_rejects_claim_when_attempts_exhausted(
    postgres_document,
):
    db = postgres_document["db"]

    job = create_test_job(postgres_document)

    job.attempts = job.max_attempts
    db.commit()

    claimed_job = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert claimed_job is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "queued"
    assert persisted_job.attempts == persisted_job.max_attempts


@pytest.mark.integration
def test_postgres_rejects_claim_for_inactive_owner(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]

    job = create_test_job(postgres_document)

    owner = db.get(User, owner_id)
    owner.is_active = False
    db.commit()

    claimed_job = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert claimed_job is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "queued"
    assert persisted_job.attempts == 0


@pytest.mark.integration
def test_postgres_rejects_claim_for_unavailable_document(
    postgres_document,
):
    db = postgres_document["db"]
    document_id = postgres_document["document_id"]

    job = create_test_job(postgres_document)

    document = db.get(Document, document_id)
    document.status = "failed"
    db.commit()

    claimed_job = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert claimed_job is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "queued"
    assert persisted_job.attempts == 0

    persisted_document = db.get(Document, document_id)

    assert persisted_document.status == "failed"

# ============================================================
# PostgreSQL retry and failure handling tests
# ============================================================

@pytest.mark.integration
def test_postgres_schedules_first_retry_with_backoff(
    postgres_document,
):
    db = postgres_document["db"]
    document_id = postgres_document["document_id"]

    job = create_test_job(postgres_document)

    # Claim the job to represent the first processing attempt.
    claimed_job = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert claimed_job is not None
    assert claimed_job.attempts == 1

    failed_job = update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="failed",
        error_code="PROCESSING_FAILED",
    )

    assert failed_job.status == "failed"

    retry_job = schedule_document_processing_retry(
        db,
        processing_job_id=job.id,
    )

    assert retry_job is not None
    assert retry_job.status == "queued"
    assert retry_job.attempts == 1

    delay = (
        retry_job.available_at - __import__(
            "datetime"
        ).datetime.now(
            __import__("datetime").timezone.utc
        )
    ).total_seconds()

    assert 29 <= delay <= 30

    document = db.get(Document, document_id)

    assert document.status == "queued"

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "queued"
    assert persisted_job.attempts == 1


@pytest.mark.integration
def test_postgres_schedules_second_retry_with_backoff(
    postgres_document,
):
    db = postgres_document["db"]
    document_id = postgres_document["document_id"]

    job = create_test_job(postgres_document)

    # Simulate two completed processing attempts.
    job.status = "failed"
    job.attempts = 2
    job.error_code = "INDEXING_FAILED"
    job.error_message = "Document indexing failed"

    document = db.get(Document, document_id)
    document.status = "failed"

    db.commit()

    retry_job = schedule_document_processing_retry(
        db,
        processing_job_id=job.id,
    )

    assert retry_job is not None
    assert retry_job.status == "queued"
    assert retry_job.attempts == 2

    delay = (
        retry_job.available_at - __import__(
            "datetime"
        ).datetime.now(
            __import__("datetime").timezone.utc
        )
    ).total_seconds()

    assert 119 <= delay <= 120

    persisted_document = db.get(Document, document_id)

    assert persisted_document.status == "queued"


@pytest.mark.integration
def test_postgres_does_not_retry_exhausted_job(
    postgres_document,
):
    db = postgres_document["db"]
    document_id = postgres_document["document_id"]

    job = create_test_job(postgres_document)

    job.status = "failed"
    job.attempts = job.max_attempts
    job.error_code = "PROCESSING_FAILED"
    job.error_message = "Document processing failed"

    document = db.get(Document, document_id)
    document.status = "failed"

    db.commit()

    retry_job = schedule_document_processing_retry(
        db,
        processing_job_id=job.id,
    )

    assert retry_job is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    persisted_document = db.get(Document, document_id)

    assert persisted_job.status == "failed"
    assert persisted_job.attempts == persisted_job.max_attempts
    assert persisted_document.status == "failed"


@pytest.mark.integration
@pytest.mark.parametrize(
    "error_code",
    [
        "SENSITIVE_DATA_SCAN_FAILED",
        "SANITIZATION_FAILED",
    ],
)
def test_postgres_never_retries_sensitive_data_failures(
    postgres_document,
    error_code,
):
    db = postgres_document["db"]
    document_id = postgres_document["document_id"]

    job = create_test_job(postgres_document)

    job.status = "failed"
    job.attempts = 1
    job.error_code = error_code
    job.error_message = error_code

    document = db.get(Document, document_id)
    document.status = "failed"

    db.commit()

    retry_job = schedule_document_processing_retry(
        db,
        processing_job_id=job.id,
    )

    assert retry_job is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    persisted_document = db.get(Document, document_id)

    assert persisted_job.status == "failed"
    assert persisted_job.error_code == error_code
    assert persisted_document.status == "failed"


@pytest.mark.integration
def test_postgres_retry_cannot_be_claimed_before_available_at(
    postgres_document,
):
    db = postgres_document["db"]

    job = create_test_job(postgres_document)

    job.status = "failed"
    job.attempts = 1
    job.error_code = "PROCESSING_FAILED"

    document = db.get(
        Document,
        postgres_document["document_id"],
    )
    document.status = "failed"

    db.commit()

    retry_job = schedule_document_processing_retry(
        db,
        processing_job_id=job.id,
    )

    assert retry_job is not None
    assert retry_job.available_at > retry_job.created_at

    # The retry is scheduled for the future.
    # The worker must not claim it prematurely.
    claimed_job = claim_document_processing_job(
        db,
        processing_job_id=job.id,
    )

    assert claimed_job is None

    persisted_job = db.get(
        DocumentProcessingJob,
        job.id,
    )

    assert persisted_job.status == "queued"
    assert persisted_job.attempts == 1


@pytest.mark.integration
def test_postgres_failed_to_queued_creates_transactional_outbox(
    postgres_document,
):
    db = postgres_document["db"]
    owner_id = postgres_document["owner_id"]
    document_id = postgres_document["document_id"]

    # Create the initial processing job.
    job = create_document_processing_job(
        db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert job is not None

    # Move the job to failed using an approved error code.
    failed_job = update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="failed",
        error_code="PROCESSING_FAILED",
    )

    assert failed_job is not None
    assert failed_job.status == "failed"

    # Make the document state consistent with the failed job.
    document = db.get(Document, document_id)
    document.status = "failed"
    db.commit()

    # Retry through the generic status-transition service.
    queued_job = update_processing_job_status(
        db,
        processing_job_id=job.id,
        status="queued",
    )

    assert queued_job is not None
    assert queued_job.status == "queued"

    # Verify the document state was updated in PostgreSQL.
    db.refresh(document)

    assert document.status == "queued"
    assert document.error_code is None
    assert document.error_message is None

    # Initial job creation and retry each create one outbox record.
    outbox_records = db.scalars(
        select(DocumentProcessingOutbox).where(
            DocumentProcessingOutbox.processing_job_id == job.id
        )
    ).all()

    assert len(outbox_records) == 2

    dispatch_ids = {
        record.dispatch_id
        for record in outbox_records
    }

    assert len(dispatch_ids) == 2

    retry_outbox_records = [
        record
        for record in outbox_records
        if record.available_at == queued_job.available_at
    ]

    assert len(retry_outbox_records) == 1
    assert retry_outbox_records[0].processing_job_id == job.id
    assert retry_outbox_records[0].dispatch_id is not None

    # Verify the job state persisted after the transaction.
    db.refresh(queued_job)

    assert queued_job.status == "queued"
    assert queued_job.error_code is None
    assert queued_job.error_message is None
