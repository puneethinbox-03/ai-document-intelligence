import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_redis_default_settings():
    settings = Settings(_env_file=None)

    assert isinstance(settings.redis_url, SecretStr)
    assert settings.redis_url.get_secret_value() == (
        "redis://127.0.0.1:6379/0"
    )


def test_redis_url_loads_from_environment(monkeypatch):
    monkeypatch.setenv(
        "REDIS_URL",
        "redis://127.0.0.1:6380/1",
    )

    settings = Settings(_env_file=None)

    assert settings.redis_url.get_secret_value() == (
        "redis://127.0.0.1:6380/1"
    )


def test_redis_url_is_masked():
    settings = Settings(
        _env_file=None,
        redis_url=(
            "redis://private-user:private-password@localhost:6379/0"
        ),
    )

    assert "private-password" not in str(settings.redis_url)
    assert "private-user" not in str(settings.redis_url)
    assert str(settings.redis_url) == "**********"


@pytest.mark.parametrize(
    "redis_url",
    [
        "http://localhost:6379",
        "ftp://localhost:6379",
        "localhost:6379",
        "redis://",
    ],
)
def test_redis_rejects_invalid_url(redis_url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, redis_url=redis_url)


def test_redis_rejects_invalid_port():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            redis_url="redis://localhost:70000/0",
        )


def test_development_accepts_local_redis():
    settings = Settings(
        _env_file=None,
        app_env="development",
        redis_url="redis://127.0.0.1:6379/0",
    )

    assert settings.redis_url.get_secret_value() == (
        "redis://127.0.0.1:6379/0"
    )


def test_production_rejects_redis_without_tls():
    with pytest.raises(
        ValueError,
        match="Production Redis must use TLS",
    ):
        Settings.validate_redis_url(
            "redis://redis.example.com:6379/0",
            production=True,
        )


def test_production_rejects_rediss_without_credentials():
    with pytest.raises(
        ValueError,
        match="ACL username and password",
    ):
        Settings.validate_redis_url(
            "rediss://redis.example.com:6379/0",
            production=True,
        )


def test_production_accepts_tls_redis_with_acl_credentials():
    Settings.validate_redis_url(
        "rediss://app-user:example-secret@redis.example.com:6379/0",
        production=True,
    )


def test_development_validation_does_not_require_tls():
    Settings.validate_redis_url(
        "redis://127.0.0.1:6379/0",
        production=False,
    )
