from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.models.document import Document
from app.models.processing_job import DocumentProcessingJob
from app.models.processing_outbox import DocumentProcessingOutbox
from app.services.document_job_service import (
    RETRYABLE_JOB_ERRORS,
    SAFE_JOB_ERRORS,
    create_document_processing_job,
    get_owned_processing_job,
    get_processing_job,
    list_owned_processing_jobs,
    schedule_document_processing_retry,
    update_processing_job_status,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def owner_id():
    return uuid4()


@pytest.fixture
def document_id():
    return uuid4()


@pytest.fixture
def job_id():
    return uuid4()


@pytest.fixture
def document(document_id, owner_id):
    return Document(
        id=document_id,
        user_id=owner_id,
        original_filename="report.pdf",
        storage_key="private/report.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        status="uploaded",
    )


@pytest.fixture
def processing_job(job_id, document_id):
    return DocumentProcessingJob(
        id=job_id,
        document_id=document_id,
        status="queued",
        attempts=0,
        max_attempts=3,
        available_at=datetime.now(timezone.utc),
    )


# ============================================================
# Job creation tests
# ============================================================

def test_create_processing_job_assigns_document_and_defaults(
    mock_db,
    document,
    owner_id,
    document_id,
):
    mock_db.scalar.side_effect = [document, None]

    result = create_document_processing_job(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert isinstance(result, DocumentProcessingJob)
    assert result.document_id == document_id
    assert result.status == "queued"
    assert result.attempts == 0
    assert result.max_attempts == 3
    assert result.available_at.tzinfo is not None

    assert document.status == "queued"
    assert document.error_code is None
    assert document.error_message is None

    added_records = [
        call.args[0]
        for call in mock_db.add.call_args_list
    ]

    assert len(added_records) == 2
    assert added_records[0] is result

    outbox_record = added_records[1]

    assert isinstance(outbox_record, DocumentProcessingOutbox)
    assert outbox_record.processing_job_id == result.id
    assert outbox_record.dispatch_id is not None
    assert outbox_record.available_at == result.available_at

    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_create_processing_job_uses_custom_attempt_limit(
    mock_db,
    document,
    owner_id,
    document_id,
):
    mock_db.scalar.side_effect = [document, None]

    result = create_document_processing_job(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
        max_attempts=5,
    )

    assert result.max_attempts == 5


def test_create_processing_job_returns_none_for_unowned_document(
    mock_db,
    owner_id,
    document_id,
):
    mock_db.scalar.return_value = None

    result = create_document_processing_job(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is None
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


def test_create_processing_job_returns_existing_active_job(
    mock_db,
    document,
    processing_job,
    owner_id,
    document_id,
):
    mock_db.scalar.side_effect = [document, processing_job]

    result = create_document_processing_job(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result is processing_job
    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()


def test_create_processing_job_rejects_ineligible_document(
    mock_db,
    document,
    owner_id,
    document_id,
):
    document.status = "deleted"
    mock_db.scalar.side_effect = [document, None]

    with pytest.raises(
        ValueError,
        match="Document is not eligible for processing",
    ):
        create_document_processing_job(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


@pytest.mark.parametrize(
    "max_attempts",
    [0, -1, 11, True, 1.5, "3"],
)
def test_create_processing_job_rejects_invalid_attempt_limit(
    mock_db,
    owner_id,
    document_id,
    max_attempts,
):
    with pytest.raises(
        ValueError,
        match="max_attempts must be between 1 and 10",
    ):
        create_document_processing_job(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            max_attempts=max_attempts,
        )

    mock_db.scalar.assert_not_called()


def test_create_processing_job_rolls_back_on_database_failure(
    mock_db,
    document,
    owner_id,
    document_id,
):
    mock_db.scalar.side_effect = [document, None]
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        create_document_processing_job(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
        )

    mock_db.rollback.assert_called_once()


def test_create_processing_job_query_locks_and_checks_owner(
    mock_db,
    document,
    owner_id,
    document_id,
):
    mock_db.scalar.side_effect = [document, None]

    create_document_processing_job(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    statement = mock_db.scalar.call_args_list[0].args[0]
    compiled = statement.compile()

    assert "documents.id" in str(compiled)
    assert "documents.user_id" in str(compiled)
    assert document_id in compiled.params.values()
    assert owner_id in compiled.params.values()
    assert statement._for_update_arg is not None


# ============================================================
# Job retrieval tests
# ============================================================

def test_get_processing_job_filters_by_job_id(
    mock_db,
    processing_job,
    job_id,
):
    mock_db.scalar.return_value = processing_job

    result = get_processing_job(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is processing_job

    statement = mock_db.scalar.call_args.args[0]
    compiled = statement.compile()

    assert "document_processing_jobs.id" in str(compiled)
    assert job_id in compiled.params.values()


def test_get_owned_processing_job_checks_document_owner(
    mock_db,
    processing_job,
    owner_id,
    job_id,
):
    mock_db.scalar.return_value = processing_job

    result = get_owned_processing_job(
        mock_db,
        processing_job_id=job_id,
        owner_id=owner_id,
    )

    assert result is processing_job

    statement = mock_db.scalar.call_args.args[0]
    compiled = statement.compile()

    assert "documents.user_id" in str(compiled)
    assert "document_processing_jobs.id" in str(compiled)
    assert owner_id in compiled.params.values()
    assert job_id in compiled.params.values()


def test_get_owned_processing_job_returns_none_for_unowned_job(
    mock_db,
    owner_id,
    job_id,
):
    mock_db.scalar.return_value = None

    result = get_owned_processing_job(
        mock_db,
        processing_job_id=job_id,
        owner_id=owner_id,
    )

    assert result is None


def test_list_owned_processing_jobs_filters_by_document_and_owner(
    mock_db,
    owner_id,
    document_id,
):
    expected_jobs = [
        MagicMock(spec=DocumentProcessingJob),
        MagicMock(spec=DocumentProcessingJob),
    ]
    mock_db.scalars.return_value.all.return_value = expected_jobs

    result = list_owned_processing_jobs(
        mock_db,
        document_id=document_id,
        owner_id=owner_id,
    )

    assert result == expected_jobs

    statement = mock_db.scalars.call_args.args[0]
    compiled = statement.compile()

    assert "documents.user_id" in str(compiled)
    assert "document_processing_jobs.document_id" in str(compiled)
    assert owner_id in compiled.params.values()
    assert document_id in compiled.params.values()


@pytest.mark.parametrize(
    ("skip", "limit"),
    [
        (-1, 10),
        (0, 0),
        (0, 101),
    ],
)
def test_list_owned_processing_jobs_rejects_invalid_pagination(
    mock_db,
    owner_id,
    document_id,
    skip,
    limit,
):
    with pytest.raises(ValueError):
        list_owned_processing_jobs(
            mock_db,
            document_id=document_id,
            owner_id=owner_id,
            skip=skip,
            limit=limit,
        )

    mock_db.scalars.assert_not_called()


# ============================================================
# Job status lifecycle tests
# ============================================================

def test_update_processing_job_to_processing_increments_attempts(
    mock_db,
    processing_job,
    job_id,
):
    mock_db.scalar.return_value = processing_job

    result = update_processing_job_status(
        mock_db,
        processing_job_id=job_id,
        status="processing",
    )

    assert result is processing_job
    assert processing_job.status == "processing"
    assert processing_job.attempts == 1
    assert processing_job.started_at is not None
    assert processing_job.completed_at is None
    assert processing_job.error_code is None
    assert processing_job.error_message is None
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_update_processing_job_to_completed_sets_completion_time(
    mock_db,
    processing_job,
    job_id,
):
    processing_job.status = "processing"
    processing_job.attempts = 1
    mock_db.scalar.return_value = processing_job

    result = update_processing_job_status(
        mock_db,
        processing_job_id=job_id,
        status="completed",
    )

    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error_code is None
    assert result.error_message is None
    mock_db.commit.assert_called_once()


def test_update_processing_job_to_failed_uses_safe_error_message(
    mock_db,
    processing_job,
    job_id,
):
    processing_job.status = "processing"
    processing_job.attempts = 1
    mock_db.scalar.return_value = processing_job

    result = update_processing_job_status(
        mock_db,
        processing_job_id=job_id,
        status="failed",
        error_code="SANITIZATION_FAILED",
    )

    assert result.status == "failed"
    assert result.error_code == "SANITIZATION_FAILED"
    assert result.error_message == SAFE_JOB_ERRORS[
        "SANITIZATION_FAILED"
    ]
    assert result.completed_at is not None


def test_update_processing_job_to_queued_clears_previous_error(
    mock_db,
    processing_job,
    document,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 1
    processing_job.error_code = "PROCESSING_FAILED"
    processing_job.error_message = SAFE_JOB_ERRORS[
        "PROCESSING_FAILED"
    ]

    document.status = "failed"

    mock_db.scalar.side_effect = [
        processing_job,
        document,
    ]

    result = update_processing_job_status(
        mock_db,
        processing_job_id=job_id,
        status="queued",
    )

    assert result is processing_job
    assert result.status == "queued"
    assert result.available_at is not None
    assert result.started_at is None
    assert result.completed_at is None
    assert result.error_code is None
    assert result.error_message is None

    assert document.status == "queued"
    assert document.error_code is None
    assert document.error_message is None

    added_records = [
        call.args[0]
        for call in mock_db.add.call_args_list
    ]

    outbox_records = [
        record
        for record in added_records
        if isinstance(record, DocumentProcessingOutbox)
    ]

    assert len(outbox_records) == 1
    assert outbox_records[0].processing_job_id == job_id
    assert isinstance(outbox_records[0].dispatch_id, UUID)
    assert outbox_records[0].available_at == result.available_at

    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_update_processing_job_returns_none_when_missing(
    mock_db,
    job_id,
):
    mock_db.scalar.return_value = None

    result = update_processing_job_status(
        mock_db,
        processing_job_id=job_id,
        status="processing",
    )

    assert result is None
    mock_db.commit.assert_not_called()


def test_update_processing_job_rejects_invalid_status(
    mock_db,
    job_id,
):
    with pytest.raises(
        ValueError,
        match="Invalid processing job status",
    ):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="unknown",
        )

    mock_db.scalar.assert_not_called()


def test_update_processing_job_rejects_invalid_transition(
    mock_db,
    processing_job,
    job_id,
):
    mock_db.scalar.return_value = processing_job

    with pytest.raises(
        ValueError,
        match="Invalid processing job status transition",
    ):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="completed",
        )

    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_update_processing_job_rejects_attempt_limit(
    mock_db,
    processing_job,
    job_id,
):
    processing_job.attempts = 3
    processing_job.max_attempts = 3
    mock_db.scalar.return_value = processing_job

    with pytest.raises(
        ValueError,
        match="attempt limit",
    ):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="processing",
        )

    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_update_processing_job_requires_safe_error_for_failure(
    mock_db,
    job_id,
):
    with pytest.raises(
        ValueError,
        match="safe error code is required",
    ):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="failed",
        )

    mock_db.scalar.assert_not_called()


def test_update_processing_job_rejects_unapproved_error_code(
    mock_db,
    job_id,
):
    with pytest.raises(
        ValueError,
        match="Invalid processing job error code",
    ):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="failed",
            error_code="Sensitive database password",
        )

    mock_db.scalar.assert_not_called()


def test_update_processing_job_rolls_back_on_commit_failure(
    mock_db,
    processing_job,
    job_id,
):
    mock_db.scalar.return_value = processing_job
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="processing",
        )

    mock_db.rollback.assert_called_once()

# ============================================================
# Retry scheduling tests
# ============================================================

def test_schedule_retry_updates_job_and_document_atomically(
    mock_db,
    processing_job,
    document,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 1
    processing_job.error_code = "PROCESSING_FAILED"
    processing_job.error_message = SAFE_JOB_ERRORS[
        "PROCESSING_FAILED"
    ]

    document.status = "processing"

    mock_db.scalar.side_effect = [
        processing_job,
        document,
    ]

    result = schedule_document_processing_retry(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is processing_job
    assert processing_job.status == "queued"
    assert processing_job.attempts == 1
    assert processing_job.available_at > datetime.now(timezone.utc)
    assert processing_job.started_at is None
    assert processing_job.completed_at is None
    assert processing_job.error_code is None
    assert processing_job.error_message is None

    assert document.status == "queued"
    assert document.error_code is None
    assert document.error_message is None

    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_schedule_retry_uses_second_backoff_delay(
    mock_db,
    processing_job,
    document,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 2
    processing_job.error_code = "INDEXING_FAILED"
    document.status = "failed"

    mock_db.scalar.side_effect = [
        processing_job,
        document,
    ]

    result = schedule_document_processing_retry(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is processing_job

    # The second retry must be scheduled approximately
    # 120 seconds after the scheduling operation.
    delay = (
        processing_job.available_at - datetime.now(timezone.utc)
    ).total_seconds()

    assert 119 <= delay <= 120
    assert processing_job.attempts == 2
    assert document.status == "queued"
    mock_db.commit.assert_called_once()


@pytest.mark.parametrize(
    "error_code",
    [
        "SENSITIVE_DATA_SCAN_FAILED",
        "SANITIZATION_FAILED",
    ],
)
def test_schedule_retry_rejects_security_failures(
    mock_db,
    processing_job,
    job_id,
    error_code,
):
    processing_job.status = "failed"
    processing_job.attempts = 1
    processing_job.error_code = error_code

    mock_db.scalar.return_value = processing_job

    result = schedule_document_processing_retry(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is None
    mock_db.scalar.assert_called_once()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_schedule_retry_rejects_exhausted_attempts(
    mock_db,
    processing_job,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 3
    processing_job.max_attempts = 3
    processing_job.error_code = "PROCESSING_FAILED"

    mock_db.scalar.return_value = processing_job

    result = schedule_document_processing_retry(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is None
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_schedule_retry_rejects_missing_document(
    mock_db,
    processing_job,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 1
    processing_job.error_code = "PROCESSING_FAILED"

    mock_db.scalar.side_effect = [
        processing_job,
        None,
    ]

    result = schedule_document_processing_retry(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is None
    assert mock_db.scalar.call_count == 2
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_schedule_retry_rejects_non_failed_job(
    mock_db,
    processing_job,
    job_id,
):
    processing_job.status = "queued"
    mock_db.scalar.return_value = processing_job

    result = schedule_document_processing_retry(
        mock_db,
        processing_job_id=job_id,
    )

    assert result is None
    mock_db.scalar.assert_called_once()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_schedule_retry_rolls_back_on_commit_failure(
    mock_db,
    processing_job,
    document,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 1
    processing_job.error_code = "PROCESSING_FAILED"
    document.status = "failed"

    mock_db.scalar.side_effect = [
        processing_job,
        document,
    ]
    mock_db.commit.side_effect = RuntimeError(
        "Database failure"
    )

    with pytest.raises(RuntimeError, match="Database failure"):
        schedule_document_processing_retry(
            mock_db,
            processing_job_id=job_id,
        )

    mock_db.rollback.assert_called_once()


def test_update_processing_job_queued_rolls_back_on_commit_failure(
    mock_db,
    processing_job,
    document,
    job_id,
):
    processing_job.status = "failed"
    processing_job.attempts = 1
    document.status = "failed"

    mock_db.scalar.side_effect = [
        processing_job,
        document,
    ]
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="queued",
        )

    mock_db.add.assert_called_once()
    mock_db.rollback.assert_called_once()


@pytest.mark.parametrize(
    ("job_status", "document_status"),
    [
        ("failed", "processing"),
        ("processing", "failed"),
    ],
)
def test_update_processing_job_to_queued_rejects_document_status_mismatch(
    mock_db,
    processing_job,
    document,
    job_id,
    job_status,
    document_status,
):
    processing_job.status = job_status
    processing_job.attempts = 1
    document.status = document_status

    mock_db.scalar.side_effect = [
        processing_job,
        document,
    ]

    with pytest.raises(
        ValueError,
        match="Document status does not match processing job status",
    ):
        update_processing_job_status(
            mock_db,
            processing_job_id=job_id,
            status="queued",
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()
