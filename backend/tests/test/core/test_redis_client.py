from unittest.mock import Mock

import pytest
from pydantic import SecretStr
from redis.exceptions import ConnectionError as RedisConnectionError

import app.core.redis_client as redis_client_module
from app.core.redis_client import (
    RedisUnavailableError,
    create_redis_client,
    verify_redis_connection,
)


def test_create_redis_client_uses_configured_secret_url(monkeypatch):
    fake_client = Mock()
    captured = {}

    def fake_from_url(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return fake_client

    monkeypatch.setattr(
        redis_client_module.Redis,
        "from_url",
        fake_from_url,
    )

    monkeypatch.setattr(
        redis_client_module.settings,
        "redis_url",
        SecretStr("redis://test-user:test-secret@127.0.0.1:6379/0"),
    )

    client = create_redis_client()

    assert client is fake_client
    assert captured["url"] == (
        "redis://test-user:test-secret@127.0.0.1:6379/0"
    )

    assert captured["kwargs"] == {
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "health_check_interval": 30,
        "decode_responses": False,
    }


def test_verify_redis_connection_succeeds():
    client = Mock()

    verify_redis_connection(client)

    client.ping.assert_called_once_with()


def test_verify_redis_connection_raises_safe_error(caplog):
    client = Mock()

    client.ping.side_effect = RedisConnectionError(
        "Connection failed: password=do-not-expose"
    )

    with pytest.raises(RedisUnavailableError) as exc_info:
        verify_redis_connection(client)

    assert str(exc_info.value) == (
        "Background processing service is unavailable"
    )

    assert "do-not-expose" not in str(exc_info.value)
    assert "do-not-expose" not in caplog.text
    assert "password=" not in caplog.text

    matching_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "redis_connection_failed"
    ]

    assert len(matching_records) == 1


def test_verify_redis_connection_does_not_expose_connection_url(
    caplog,
):
    client = Mock()

    client.ping.side_effect = RedisConnectionError(
        "redis://secret-user:secret-password@localhost:6379/0"
    )

    with pytest.raises(RedisUnavailableError) as exc_info:
        verify_redis_connection(client)

    assert "secret-user" not in str(exc_info.value)
    assert "secret-password" not in str(exc_info.value)
    assert "secret-password" not in caplog.text
