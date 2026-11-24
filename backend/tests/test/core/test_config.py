
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


# ------------------------------------------------------------
# PostgreSQL configuration tests
# ------------------------------------------------------------

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
        Settings(_env_file=None, postgres_port=70000)


# ------------------------------------------------------------
# Existing RAG and storage tests
# ------------------------------------------------------------

def test_existing_rag_settings_are_preserved():
    settings = Settings(_env_file=None)

    assert settings.rag_llm_provider == "mock"
    assert settings.ollama_model == "qwen3:8b-q4_K_M"
    assert settings.ollama_url == "http://localhost:11434"


def test_existing_storage_paths_are_preserved():
    settings = Settings(_env_file=None)

    assert settings.upload_dir.is_absolute()
    assert settings.chroma_path.is_absolute()


# ------------------------------------------------------------
# Authentication defaults
# ------------------------------------------------------------

def test_authentication_default_settings():
    settings = Settings(_env_file=None)

    assert settings.frontend_url == "http://localhost:3000"
    assert settings.session_cookie_name == "adi_session"
    assert settings.csrf_cookie_name == "adi_csrf"
    assert settings.session_lifetime_hours == 24
    assert settings.session_cookie_secure is False
    assert settings.session_cookie_samesite == "lax"
    assert settings.session_cookie_path == "/"
    assert settings.email_verification_token_lifetime_minutes == 1440
    assert settings.password_reset_token_lifetime_minutes == 30
    assert settings.password_min_length == 12
    assert settings.password_max_length == 128
    assert settings.csrf_protection_enabled is True


def test_authentication_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://example.com")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_session")
    monkeypatch.setenv("SESSION_LIFETIME_HOURS", "48")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "strict")
    monkeypatch.setenv(
        "EMAIL_VERIFICATION_TOKEN_LIFETIME_MINUTES",
        "720",
    )
    monkeypatch.setenv(
        "PASSWORD_RESET_TOKEN_LIFETIME_MINUTES",
        "15",
    )

    settings = Settings(_env_file=None)

    assert settings.frontend_url == "https://example.com"
    assert settings.session_cookie_name == "custom_session"
    assert settings.session_lifetime_hours == 48
    assert settings.session_cookie_secure is True
    assert settings.session_cookie_samesite == "strict"
    assert settings.email_verification_token_lifetime_minutes == 720
    assert settings.password_reset_token_lifetime_minutes == 15


def test_session_lifetime_rejects_invalid_values():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, session_lifetime_hours=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, session_lifetime_hours=721)


def test_verification_token_lifetime_rejects_invalid_values():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            email_verification_token_lifetime_minutes=0,
        )


def test_password_reset_lifetime_rejects_invalid_values():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            password_reset_token_lifetime_minutes=1441,
        )


def test_password_length_rejects_invalid_minimum():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, password_min_length=7)


def test_password_length_rejects_minimum_greater_than_maximum():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            password_min_length=20,
            password_max_length=16,
        )


# ------------------------------------------------------------
# Security configuration validation
# ------------------------------------------------------------

def test_production_requires_debug_disabled():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            debug=True,
            session_cookie_secure=True,
        )


def test_production_requires_secure_session_cookie():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            debug=False,
            session_cookie_secure=False,
        )


def test_production_accepts_secure_session_cookie():
    settings = Settings(
        _env_file=None,
        app_env="production",
        debug=False,
        session_cookie_secure=True,
    )

    assert settings.app_env == "production"
    assert settings.session_cookie_secure is True


def test_samesite_none_requires_secure_cookie():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            session_cookie_samesite="none",
            session_cookie_secure=False,
        )


def test_samesite_none_accepts_secure_cookie():
    settings = Settings(
        _env_file=None,
        session_cookie_samesite="none",
        session_cookie_secure=True,
    )

    assert settings.session_cookie_samesite == "none"
    assert settings.session_cookie_secure is True


# ------------------------------------------------------------
# SMTP configuration tests
# ------------------------------------------------------------

def test_smtp_default_settings():
    settings = Settings(_env_file=None)

    assert settings.smtp_host is None
    assert settings.smtp_port == 587
    assert settings.smtp_username is None
    assert settings.smtp_password.get_secret_value() == ""
    assert settings.smtp_from_email is None
    assert settings.smtp_from_name == (
        "AI Document Intelligence Assistant"
    )
    assert settings.smtp_starttls is True
    assert settings.smtp_timeout_seconds == 10.0


def test_smtp_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-secret")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "ADI Mail")
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setenv("SMTP_TIMEOUT_SECONDS", "15")

    settings = Settings(_env_file=None)

    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_port == 587
    assert settings.smtp_username == "smtp-user"
    assert settings.smtp_password.get_secret_value() == "smtp-secret"
    assert str(settings.smtp_from_email) == "no-reply@example.com"
    assert settings.smtp_from_name == "ADI Mail"
    assert settings.smtp_starttls is True
    assert settings.smtp_timeout_seconds == 15.0


def test_smtp_password_is_masked():
    settings = Settings(
        _env_file=None,
        smtp_username="smtp-user",
        smtp_password="smtp-local-secret",
    )

    assert "smtp-local-secret" not in str(settings.smtp_password)
    assert str(settings.smtp_password) == "**********"


def test_smtp_port_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, smtp_port=70000)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, smtp_port=0)


def test_smtp_requires_sender_email_when_enabled():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            smtp_host="smtp.example.com",
        )


def test_smtp_requires_username_and_password_together():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            smtp_username="smtp-user",
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            smtp_password="smtp-secret",
        )


def test_smtp_requires_starttls_when_enabled():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            smtp_host="smtp.example.com",
            smtp_from_email="no-reply@example.com",
            smtp_starttls=False,
        )


def test_smtp_accepts_valid_configuration():
    settings = Settings(
        _env_file=None,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="smtp-user",
        smtp_password="smtp-secret",
        smtp_from_email="no-reply@example.com",
        smtp_from_name="ADI Mail",
        smtp_starttls=True,
    )

    assert settings.smtp_host == "smtp.example.com"
    assert settings.smtp_username == "smtp-user"
    assert settings.smtp_password.get_secret_value() == "smtp-secret"
    assert str(settings.smtp_from_email) == "no-reply@example.com"
