
from uuid import uuid4

import pytest

from app.workers import document_worker


def test_invalid_job_identifier_is_rejected():
    with pytest.raises(
        document_worker.DocumentWorkerError,
        match="Invalid document-processing job identifier",
    ):
        document_worker.process_document_job("not-a-uuid")


def test_valid_job_is_deferred_until_secure_processor_exists(
    caplog,
):
    job_id = uuid4()

    with caplog.at_level("WARNING"):
        result = document_worker.process_document_job(str(job_id))

    assert result == {
        "status": "deferred",
        "reason": "secure_processor_not_configured",
        "processing_job_id": str(job_id),
    }

    assert any(
        getattr(record, "event", None) == "document_job_deferred"
        and getattr(record, "processing_job_id", None) == str(job_id)
        for record in caplog.records
    )


def test_deferred_job_does_not_access_database(monkeypatch):
    def unexpected_database_access():
        pytest.fail(
            "Deferred worker must not access PostgreSQL"
        )

    monkeypatch.setattr(
        document_worker,
        "SessionLocal",
        unexpected_database_access,
        raising=False,
    )

    result = document_worker.process_document_job(str(uuid4()))

    assert result["status"] == "deferred"


def test_deferred_job_does_not_log_document_content(caplog):
    job_id = uuid4()

    with caplog.at_level("WARNING"):
        document_worker.process_document_job(str(job_id))

    matching_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "document_job_deferred"
    ]

    assert len(matching_records) == 1
    assert matching_records[0].processing_job_id == str(job_id)

    log_content = caplog.text.lower()

    assert "document content" not in log_content
    assert "password" not in log_content
    assert "token" not in log_content
