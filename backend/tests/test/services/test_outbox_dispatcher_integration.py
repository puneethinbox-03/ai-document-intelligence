import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import app.models

from app.core.database import SessionLocal
from app.models import (
    Document,
    DocumentProcessingJob,
    DocumentProcessingOutbox,
    User,
)
from app.services.outbox_dispatcher_service import (
    _claim_pending_outbox_records,
    _claim_dispatched_outbox_records,
    _mark_outbox_dispatched,
    _reopen_dispatched_outbox_record,
    _release_reconciliation_lease,
    _schedule_outbox_delivery_retry,
    dispatch_pending_document_jobs,
    reconcile_dispatched_document_jobs,
)

@pytest.fixture
def postgres_outbox_record():
    db: Session = SessionLocal()

    owner_id = None
    document_id = uuid.uuid4()
    job_id = uuid.uuid4()
    outbox_id = uuid.uuid4()

    unique_value = uuid.uuid4().hex
    email = f"outbox-integration-{unique_value}@example.test"

    try:
        user = User(
            email=email,
            email_normalized=email,
            password_hash="integration-test-placeholder",
            display_name="Outbox Integration Test",
        )

        db.add(user)
        db.flush()

        owner_id = user.id

        document = Document(
            id=document_id,
            user_id=owner_id,
            original_filename="outbox-test.pdf",
            storage_key=f"outbox-tests/{unique_value}.pdf",
            content_type="application/pdf",
            file_size_bytes=100,
            status="queued",
        )

        db.add(document)
        db.flush()

        now = datetime.now(timezone.utc)

        job = DocumentProcessingJob(
            id=job_id,
            document_id=document_id,
            status="queued",
            attempts=0,
            max_attempts=3,
            available_at=now,
        )

        db.add(job)
        db.flush()

        outbox = DocumentProcessingOutbox(
            id=outbox_id,
            processing_job_id=job_id,
            dispatch_id=uuid.uuid4(),
            available_at=now,
            delivery_attempts=0,
        )

        db.add(outbox)
        db.commit()

        yield {
            "db": db,
            "outbox_id": outbox_id,
            "job_id": job_id,
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


@pytest.mark.integration
def test_postgres_claims_due_outbox_record(
    postgres_outbox_record,
):
    record = postgres_outbox_record

    claimed = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    matching = [
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    ]

    assert len(matching) == 1

    claimed_record = matching[0]

    assert claimed_record["processing_job_id"] == record["job_id"]
    assert claimed_record["delivery_attempts"] == 1
    assert claimed_record["lease_token"] is not None

    db = record["db"]

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.lease_token == claimed_record["lease_token"]
    assert persisted.lease_expires_at is not None
    assert persisted.delivery_attempts == 1


@pytest.mark.integration
def test_postgres_does_not_claim_record_with_active_lease(
    postgres_outbox_record,
):
    record = postgres_outbox_record

    first_claim = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    matching = [
        item for item in first_claim
        if item["outbox_id"] == record["outbox_id"]
    ]

    assert len(matching) == 1

    second_claim = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    assert not any(
        item["outbox_id"] == record["outbox_id"]
        for item in second_claim
    )


@pytest.mark.integration
def test_postgres_marks_outbox_dispatched_with_valid_lease(
    postgres_outbox_record,
):
    record = postgres_outbox_record

    claimed = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    marked = _mark_outbox_dispatched(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=claimed_record["lease_token"],
    )

    assert marked is True

    db = record["db"]

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is not None
    assert persisted.lease_token is None
    assert persisted.lease_expires_at is None
    assert persisted.last_error_code is None


@pytest.mark.integration
def test_postgres_rejects_stale_lease_token(
    postgres_outbox_record,
):
    record = postgres_outbox_record

    claimed = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    stale_token = uuid.uuid4()

    marked = _mark_outbox_dispatched(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=stale_token,
    )

    assert marked is False

    db = record["db"]

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is None
    assert persisted.lease_token == claimed_record["lease_token"]


@pytest.mark.integration
def test_postgres_schedules_failed_delivery_retry(
    postgres_outbox_record,
):
    record = postgres_outbox_record

    claimed = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    released = _schedule_outbox_delivery_retry(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=claimed_record["lease_token"],
        delivery_attempts=claimed_record["delivery_attempts"],
    )

    assert released is True

    db = record["db"]

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is None
    assert persisted.lease_token is None
    assert persisted.lease_expires_at is not None
    assert persisted.lease_expires_at > datetime.now(timezone.utc)
    assert persisted.last_error_code == "QUEUE_UNAVAILABLE"


@pytest.mark.integration
def test_postgres_does_not_release_record_with_stale_token(
    postgres_outbox_record,
):
    record = postgres_outbox_record

    claimed = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    released = _schedule_outbox_delivery_retry(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=uuid.uuid4(),
        delivery_attempts=claimed_record["delivery_attempts"],
    )

    assert released is False

    db = record["db"]

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.lease_token == claimed_record["lease_token"]
    assert persisted.last_error_code is None


@pytest.mark.integration
def test_postgres_does_not_claim_future_outbox_record(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    persisted.available_at = (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    )

    db.commit()

    claimed = _claim_pending_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    assert not any(
        item["outbox_id"] == record["outbox_id"]
        for item in claimed
    )

@pytest.mark.integration
def test_postgres_claims_dispatched_queued_record(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    original_dispatch_id = outbox.dispatch_id
    outbox.dispatched_at = datetime.now(timezone.utc)
    db.commit()

    claimed = _claim_dispatched_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    matching = [
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    ]

    assert len(matching) == 1

    claimed_record = matching[0]

    assert claimed_record["processing_job_id"] == record["job_id"]
    assert claimed_record["dispatch_id"] == original_dispatch_id
    assert claimed_record["lease_token"] is not None

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is not None
    assert persisted.lease_token == claimed_record["lease_token"]
    assert persisted.lease_expires_at is not None


@pytest.mark.integration
def test_postgres_does_not_claim_dispatched_record_with_active_lease(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    outbox.dispatched_at = datetime.now(timezone.utc)
    outbox.lease_token = uuid.uuid4()
    outbox.lease_expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db.commit()

    claimed = _claim_dispatched_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    assert not any(
        item["outbox_id"] == record["outbox_id"]
        for item in claimed
    )


@pytest.mark.integration
def test_postgres_reopens_missing_dispatched_record(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    original_dispatch_id = outbox.dispatch_id
    outbox.dispatched_at = datetime.now(timezone.utc)
    db.commit()

    claimed = _claim_dispatched_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    reopened = _reopen_dispatched_outbox_record(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=claimed_record["lease_token"],
    )

    assert reopened is True

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is None
    assert persisted.lease_token is None
    assert persisted.lease_expires_at is None
    assert persisted.available_at <= datetime.now(timezone.utc)
    assert persisted.dispatch_id == original_dispatch_id
    assert persisted.last_error_code == "REDIS_JOB_NOT_ACTIVE"


@pytest.mark.integration
def test_postgres_reconciliation_rejects_stale_lease(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    outbox.dispatched_at = datetime.now(timezone.utc)
    db.commit()

    claimed = _claim_dispatched_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    reopened = _reopen_dispatched_outbox_record(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=uuid.uuid4(),
    )

    assert reopened is False

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is not None
    assert persisted.lease_token == claimed_record["lease_token"]


@pytest.mark.integration
def test_postgres_does_not_reopen_job_that_started_processing(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    outbox.dispatched_at = datetime.now(timezone.utc)
    db.commit()

    claimed = _claim_dispatched_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    job = db.get(
        DocumentProcessingJob,
        record["job_id"],
    )

    job.status = "processing"
    db.commit()

    reopened = _reopen_dispatched_outbox_record(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=claimed_record["lease_token"],
    )

    assert reopened is False

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is not None


@pytest.mark.integration
def test_postgres_releases_reconciliation_lease_with_cooldown(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    outbox.dispatched_at = datetime.now(timezone.utc)
    db.commit()

    claimed = _claim_dispatched_outbox_records(
        SessionLocal,
        batch_size=10,
    )

    claimed_record = next(
        item for item in claimed
        if item["outbox_id"] == record["outbox_id"]
    )

    released = _release_reconciliation_lease(
        SessionLocal,
        outbox_id=record["outbox_id"],
        lease_token=claimed_record["lease_token"],
    )

    assert released is True

    db.expire_all()

    persisted = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert persisted.dispatched_at is not None
    assert persisted.lease_token is None
    assert persisted.lease_expires_at is not None
    assert persisted.lease_expires_at > datetime.now(timezone.utc)

@pytest.mark.integration
def test_postgres_recovers_missing_redis_dispatch_and_redelivers_with_same_id(
    postgres_outbox_record,
):
    record = postgres_outbox_record
    db = record["db"]

    # Simulate a job that PostgreSQL believes was already dispatched.
    outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    original_dispatch_id = outbox.dispatch_id
    outbox.dispatched_at = datetime.now(timezone.utc)
    db.commit()

    # Simulate Redis confirming that the previously dispatched
    # job no longer exists.
    verification_calls = []

    def verify_missing(processing_job_id, dispatch_id):
        verification_calls.append(
            (processing_job_id, dispatch_id)
        )
        return "missing"

    reconciliation_result = reconcile_dispatched_document_jobs(
        batch_size=10,
        session_factory=SessionLocal,
        verify_func=verify_missing,
    )

    assert reconciliation_result["claimed"] >= 1
    assert reconciliation_result["reopened"] == 1
    assert verification_calls == [
        (record["job_id"], original_dispatch_id),
    ]

    # Confirm PostgreSQL reopened the same outbox record and
    # preserved its original stable dispatch ID.
    db.expire_all()

    reopened_outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert reopened_outbox.dispatched_at is None
    assert reopened_outbox.dispatch_id == original_dispatch_id
    assert reopened_outbox.lease_token is None
    assert reopened_outbox.lease_expires_at is None
    assert reopened_outbox.last_error_code == "REDIS_JOB_NOT_ACTIVE"

    # Simulate Redis accepting the redelivery.
    enqueue_calls = []

    def mock_enqueue(processing_job_id, *, dispatch_id):
        enqueue_calls.append(
            (processing_job_id, dispatch_id)
        )

    dispatch_result = dispatch_pending_document_jobs(
        batch_size=10,
        session_factory=SessionLocal,
        enqueue_func=mock_enqueue,
    )

    assert dispatch_result["claimed"] >= 1
    assert dispatch_result["dispatched"] == 1
    assert dispatch_result["failed"] == 0
    assert enqueue_calls == [
        (record["job_id"], original_dispatch_id),
    ]

    # Verify PostgreSQL recorded the successful redelivery.
    db.expire_all()

    final_outbox = db.get(
        DocumentProcessingOutbox,
        record["outbox_id"],
    )

    assert final_outbox.dispatched_at is not None
    assert final_outbox.dispatch_id == original_dispatch_id
    assert final_outbox.lease_token is None
    assert final_outbox.lease_expires_at is None
    assert final_outbox.last_error_code is None