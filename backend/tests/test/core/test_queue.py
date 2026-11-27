from unittest.mock import Mock

from rq import Queue
from rq.serializers import JSONSerializer

import app.core.queue as queue_module
from app.core.queue import (
    DOCUMENT_PROCESSING_JOB_TIMEOUT_SECONDS,
    DOCUMENT_PROCESSING_QUEUE_NAME,
    create_document_processing_queue,
)


def test_create_queue_uses_expected_name_and_timeout():
    connection = Mock()

    queue = create_document_processing_queue(connection=connection)

    assert isinstance(queue, Queue)
    assert queue.name == DOCUMENT_PROCESSING_QUEUE_NAME
    assert queue.name == "document_processing"
    assert queue.connection is connection

    # RQ 3.0.0 stores the configured default timeout internally.
    assert queue._default_timeout == (
        DOCUMENT_PROCESSING_JOB_TIMEOUT_SECONDS
    )
    assert queue._default_timeout == 900


def test_create_queue_uses_json_serializer():
    connection = Mock()

    queue = create_document_processing_queue(connection=connection)

    assert queue.serializer is JSONSerializer


def test_create_queue_is_asynchronous():
    connection = Mock()

    queue = create_document_processing_queue(connection=connection)

    assert queue.is_async is True


def test_create_queue_uses_configured_redis_client(monkeypatch):
    fake_connection = Mock()

    monkeypatch.setattr(
        queue_module,
        "create_redis_client",
        lambda: fake_connection,
    )

    queue = create_document_processing_queue()

    assert queue.connection is fake_connection
    assert queue.serializer is JSONSerializer
