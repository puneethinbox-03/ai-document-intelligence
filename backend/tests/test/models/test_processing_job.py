from sqlalchemy import DateTime, ForeignKey, Integer, String

from app.models.processing_job import DocumentProcessingJob


def test_processing_job_uses_expected_table_name():
    assert DocumentProcessingJob.__tablename__ == "document_processing_jobs"


def test_processing_job_has_expected_columns():
    expected_columns = {
        "id",
        "document_id",
        "status",
        "attempts",
        "max_attempts",
        "available_at",
        "started_at",
        "completed_at",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(
        set(DocumentProcessingJob.__table__.columns.keys())
    )


def test_processing_job_document_foreign_key():
    column = DocumentProcessingJob.__table__.c.document_id

    assert column.nullable is False
    assert len(column.foreign_keys) == 1

    foreign_key = next(iter(column.foreign_keys))
    assert foreign_key.target_fullname == "documents.id"


def test_processing_job_status_defaults_to_queued():
    column = DocumentProcessingJob.__table__.c.status

    assert isinstance(column.type, String)
    assert column.type.length == 20
    assert column.nullable is False
    assert column.default.arg == "queued"
    assert str(column.server_default.arg) == "queued"


def test_processing_job_attempt_defaults():
    attempts = DocumentProcessingJob.__table__.c.attempts
    max_attempts = DocumentProcessingJob.__table__.c.max_attempts

    assert isinstance(attempts.type, Integer)
    assert attempts.nullable is False
    assert attempts.default.arg == 0
    assert str(attempts.server_default.arg) == "0"

    assert isinstance(max_attempts.type, Integer)
    assert max_attempts.nullable is False
    assert max_attempts.default.arg == 3
    assert str(max_attempts.server_default.arg) == "3"


def test_processing_job_available_at_is_required_and_timezone_aware():
    column = DocumentProcessingJob.__table__.c.available_at

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is False


def test_processing_job_execution_timestamps_are_optional():
    for column_name in ("started_at", "completed_at"):
        column = DocumentProcessingJob.__table__.c[column_name]

        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is True


def test_processing_job_error_fields_are_optional():
    error_code = DocumentProcessingJob.__table__.c.error_code
    error_message = DocumentProcessingJob.__table__.c.error_message

    assert isinstance(error_code.type, String)
    assert error_code.type.length == 100
    assert error_code.nullable is True

    assert isinstance(error_message.type, String)
    assert error_message.type.length == 500
    assert error_message.nullable is True


def test_processing_job_check_constraints():
    from sqlalchemy import CheckConstraint

    constraints = {
        constraint.name
        for constraint in DocumentProcessingJob.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints == {
        "ck_document_processing_jobs_status_valid",
        "ck_document_processing_jobs_attempts_non_negative",
        "ck_document_processing_jobs_max_attempts_positive",
        "ck_document_processing_jobs_attempts_within_limit",
    }


def test_processing_job_status_available_at_index():
    indexes = {
        index.name: index
        for index in DocumentProcessingJob.__table__.indexes
    }

    index = indexes[
        "ix_document_processing_jobs_status_available_at"
    ]

    assert [column.name for column in index.columns] == [
        "status",
        "available_at",
    ]


def test_processing_job_document_id_index():
    indexes = {
        index.name: index
        for index in DocumentProcessingJob.__table__.indexes
    }

    index = indexes["ix_document_processing_jobs_document_id"]

    assert [column.name for column in index.columns] == [
        "document_id",
    ]


def test_processing_job_document_foreign_key_cascades_on_delete():
    foreign_keys = list(
        DocumentProcessingJob.__table__.c.document_id.foreign_keys
    )

    assert len(foreign_keys) == 1
    assert foreign_keys[0].ondelete == "CASCADE"
