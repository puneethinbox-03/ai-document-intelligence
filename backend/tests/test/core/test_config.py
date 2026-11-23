import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_postgres_default_settings():
    settings = Settings(_env_file=None)

    assert settings.postgres_host == "localhost"
    assert settings.postgres_port == 5432
    assert settings.postgres_db == "ai_document_intelligence"
    assert settings.postgres_user == "ai_document_app"
    assert isinstance(settings.postgres_password, SecretStr)
    assert settings.postgres_password.get_secret_value() == ""


def test_postgres_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "test_database")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-secret")

    settings = Settings(_env_file=None)

    assert settings.postgres_host == "127.0.0.1"
    assert settings.postgres_port == 5433
    assert settings.postgres_db == "test_database"
    assert settings.postgres_user == "test_user"
    assert settings.postgres_password.get_secret_value() == "test-secret"


def test_postgres_password_is_masked():
    settings = Settings(
        _env_file=None,
        postgres_password="my-local-secret",
    )

    assert "my-local-secret" not in str(settings.postgres_password)
    assert str(settings.postgres_password) == "**********"


def test_postgres_port_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            postgres_port=70000,
        )


def test_existing_rag_settings_are_preserved():
    settings = Settings(_env_file=None)

    assert settings.rag_llm_provider == "mock"
    assert settings.ollama_model == "qwen3:8b-q4_K_M"
    assert settings.ollama_url == "http://localhost:11434"


def test_existing_storage_paths_are_preserved():
    settings = Settings(_env_file=None)

    assert settings.upload_dir.is_absolute()
    assert settings.chroma_path.is_absolute()
