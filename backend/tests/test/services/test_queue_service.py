from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from rq.exceptions import DuplicateJobError
from rq.job import JobStatus
from rq.exceptions import NoSuchJobError

import app.services.queue_service as queue_service_module
from app.services.queue_service import (
    DOCUMENT_PROCESSING_FUNCTION,
    QueueEnqueueError,
    enqueue_document_processing,
    DISPATCH_ACTIVE,
    DISPATCH_MISSING,
    DISPATCH_TERMINAL,
    DISPATCH_UNVERIFIED,
    verify_document_processing_dispatch,
)


def test_enqueue_uses_supplied_stable_dispatch_id(monkeypatch):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_job = Mock()
    fake_queue = Mock()
    fake_queue.enqueue.return_value = fake_job

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    result = enqueue_document_processing(
        processing_job_id,
        dispatch_id,
    )

    assert result is fake_job

    args, kwargs = fake_queue.enqueue.call_args

    assert args == (
        DOCUMENT_PROCESSING_FUNCTION,
        str(processing_job_id),
    )
    assert kwargs["job_id"] == str(dispatch_id)
    assert kwargs["unique"] is True
    assert kwargs["job_timeout"] == 900


def test_enqueue_generates_dispatch_id_when_not_supplied(monkeypatch):
    processing_job_id = uuid4()
    fake_queue = Mock()

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    enqueue_document_processing(processing_job_id)

    _, kwargs = fake_queue.enqueue.call_args

    assert UUID(kwargs["job_id"])
    assert kwargs["job_id"] != str(processing_job_id)


def test_duplicate_delivery_returns_verified_existing_job(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()
    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = JobStatus.QUEUED

    fake_queue.enqueue.side_effect = DuplicateJobError(
        "Duplicate job"
    )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    fetch_mock = Mock(return_value=existing_job)

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        fetch_mock,
    )

    result = enqueue_document_processing(
        processing_job_id,
        dispatch_id,
    )

    assert result is existing_job

    fetch_mock.assert_called_once_with(
        str(dispatch_id),
        connection=fake_queue.connection,
        serializer=queue_service_module.JSONSerializer,
    )


def test_duplicate_delivery_rejects_different_payload(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()
    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(uuid4()),)
    existing_job.kwargs = {}

    fake_queue.enqueue.side_effect = DuplicateJobError(
        "Duplicate job"
    )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    with pytest.raises(QueueEnqueueError) as exc_info:
        enqueue_document_processing(
            processing_job_id,
            dispatch_id,
        )

    assert str(exc_info.value) == (
        "Document processing dispatch could not be verified"
    )


def test_duplicate_delivery_rejects_wrong_function(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()
    existing_job = Mock()
    existing_job.func_name = "unexpected.function"
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}

    fake_queue.enqueue.side_effect = DuplicateJobError(
        "Duplicate job"
    )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    with pytest.raises(QueueEnqueueError):
        enqueue_document_processing(
            processing_job_id,
            dispatch_id,
        )


def test_enqueue_rejects_non_uuid_processing_job_id():
    with pytest.raises(TypeError) as exc_info:
        enqueue_document_processing("not-a-uuid")

    assert str(exc_info.value) == (
        "processing_job_id must be a UUID"
    )


def test_enqueue_rejects_non_uuid_dispatch_id():
    with pytest.raises(TypeError) as exc_info:
        enqueue_document_processing(
            uuid4(),
            "not-a-uuid",
        )

    assert str(exc_info.value) == (
        "dispatch_id must be a UUID"
    )


def test_enqueue_wraps_queue_failure_without_exposing_details(
    monkeypatch,
    caplog,
):
    fake_queue = Mock()

    fake_queue.enqueue.side_effect = RuntimeError(
        "redis://user:secret-password@localhost:6379"
    )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    with pytest.raises(QueueEnqueueError) as exc_info:
        enqueue_document_processing(uuid4(), uuid4())

    assert str(exc_info.value) == (
        "Document processing could not be scheduled"
    )

    assert "secret-password" not in str(exc_info.value)
    assert "secret-password" not in caplog.text
    assert "redis://" not in caplog.text


def test_enqueue_wraps_redis_connection_failure(
    monkeypatch,
    caplog,
):
    def fail_to_connect():
        raise RuntimeError(
            "redis://user:secret-password@localhost:6379"
        )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        fail_to_connect,
    )

    with pytest.raises(QueueEnqueueError) as exc_info:
        enqueue_document_processing(uuid4(), uuid4())

    assert str(exc_info.value) == (
        "Document processing could not be scheduled"
    )

    assert "secret-password" not in caplog.text
    assert "redis://" not in caplog.text


def test_enqueue_does_not_create_queue_for_invalid_identifier(
    monkeypatch,
):
    queue_factory = Mock()

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        queue_factory,
    )

    with pytest.raises(TypeError):
        enqueue_document_processing(123)

    queue_factory.assert_not_called()


def test_duplicate_finished_delivery_is_deleted_and_reenqueued(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()

    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = JobStatus.FINISHED

    replacement_job = Mock()

    fake_queue.enqueue.side_effect = [
        DuplicateJobError("Duplicate job"),
        replacement_job,
    ]

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    result = enqueue_document_processing(
        processing_job_id,
        dispatch_id,
    )

    assert result is replacement_job
    existing_job.delete.assert_called_once()
    assert fake_queue.enqueue.call_count == 2

    retry_args, retry_kwargs = fake_queue.enqueue.call_args

    assert retry_args == (
        DOCUMENT_PROCESSING_FUNCTION,
        str(processing_job_id),
    )
    assert retry_kwargs["job_id"] == str(dispatch_id)
    assert retry_kwargs["unique"] is True


def test_duplicate_failed_delivery_is_deleted_and_reenqueued(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()

    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = JobStatus.FAILED

    replacement_job = Mock()

    fake_queue.enqueue.side_effect = [
        DuplicateJobError("Duplicate job"),
        replacement_job,
    ]

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    result = enqueue_document_processing(
        processing_job_id,
        dispatch_id,
    )

    assert result is replacement_job
    existing_job.delete.assert_called_once()
    assert fake_queue.enqueue.call_count == 2

    retry_args, retry_kwargs = fake_queue.enqueue.call_args

    assert retry_args == (
        DOCUMENT_PROCESSING_FUNCTION,
        str(processing_job_id),
    )
    assert retry_kwargs["job_id"] == str(dispatch_id)
    assert retry_kwargs["unique"] is True


def test_duplicate_delivery_rejects_unsupported_status(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()
    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = None

    fake_queue.enqueue.side_effect = DuplicateJobError(
        "Duplicate job"
    )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    with pytest.raises(
        QueueEnqueueError,
        match="could not be verified",
    ):
        enqueue_document_processing(
            processing_job_id,
            dispatch_id,
        )

    existing_job.delete.assert_not_called()
    fake_queue.enqueue.assert_called_once()


def test_verify_dispatch_returns_active_for_matching_queued_job(
    monkeypatch,
):
    processing_job_id = uuid4()
    dispatch_id = uuid4()

    fake_queue = Mock()
    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = JobStatus.QUEUED

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    fetch_mock = Mock(return_value=existing_job)

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        fetch_mock,
    )

    result = verify_document_processing_dispatch(
        processing_job_id,
        dispatch_id,
    )

    assert result == DISPATCH_ACTIVE

    fetch_mock.assert_called_once_with(
        str(dispatch_id),
        connection=fake_queue.connection,
        serializer=queue_service_module.JSONSerializer,
    )

    existing_job.get_status.assert_called_once_with(refresh=True)
    existing_job.delete.assert_not_called()


def test_verify_dispatch_returns_missing_when_job_does_not_exist(
    monkeypatch,
):
    fake_queue = Mock()

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(side_effect=NoSuchJobError("Not found")),
    )

    result = verify_document_processing_dispatch(
        uuid4(),
        uuid4(),
    )

    assert result == DISPATCH_MISSING


def test_verify_dispatch_returns_terminal_for_finished_job(
    monkeypatch,
):
    processing_job_id = uuid4()
    fake_queue = Mock()

    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = JobStatus.FINISHED

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    result = verify_document_processing_dispatch(
        processing_job_id,
        uuid4(),
    )

    assert result == DISPATCH_TERMINAL
    existing_job.delete.assert_not_called()


def test_verify_dispatch_rejects_wrong_payload(
    monkeypatch,
):
    processing_job_id = uuid4()
    fake_queue = Mock()

    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(uuid4()),)
    existing_job.kwargs = {}

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    result = verify_document_processing_dispatch(
        processing_job_id,
        uuid4(),
    )

    assert result == DISPATCH_UNVERIFIED
    existing_job.get_status.assert_not_called()
    existing_job.delete.assert_not_called()


def test_verify_dispatch_returns_unverified_when_redis_unavailable(
    monkeypatch,
    caplog,
):
    def fail_to_connect():
        raise RuntimeError(
            "redis://user:secret-password@localhost:6379"
        )

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        fail_to_connect,
    )

    result = verify_document_processing_dispatch(
        uuid4(),
        uuid4(),
    )

    assert result == DISPATCH_UNVERIFIED
    assert "secret-password" not in caplog.text
    assert "redis://" not in caplog.text


def test_verify_dispatch_returns_unverified_for_unknown_status(
    monkeypatch,
):
    processing_job_id = uuid4()
    fake_queue = Mock()

    existing_job = Mock()
    existing_job.func_name = DOCUMENT_PROCESSING_FUNCTION
    existing_job.args = (str(processing_job_id),)
    existing_job.kwargs = {}
    existing_job.get_status.return_value = None

    monkeypatch.setattr(
        queue_service_module,
        "create_document_processing_queue",
        lambda: fake_queue,
    )

    monkeypatch.setattr(
        queue_service_module.Job,
        "fetch",
        Mock(return_value=existing_job),
    )

    result = verify_document_processing_dispatch(
        processing_job_id,
        uuid4(),
    )

    assert result == DISPATCH_UNVERIFIED
    existing_job.delete.assert_not_called()


@pytest.mark.parametrize(
    "processing_job_id, dispatch_id",
    [
        ("invalid", uuid4()),
        (uuid4(), "invalid"),
    ],
)
def test_verify_dispatch_rejects_invalid_identifiers(
    processing_job_id,
    dispatch_id,
):
    with pytest.raises(TypeError):
        verify_document_processing_dispatch(
            processing_job_id,
            dispatch_id,
        )
