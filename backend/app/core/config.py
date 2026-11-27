from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


# ------------------------------------------------------------
# Backend directory
# ------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------
# Application settings
# ------------------------------------------------------------

class Settings(BaseSettings):
    """
    Centralized application configuration.

    Configuration priority:
        1. Environment variables
        2. backend/.env
        3. Default values
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AI Document Intelligence Assistant"
    app_version: str = "0.1.0"

    app_env: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    debug: bool = True
    api_prefix: str = "/api"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # Authentication
    session_cookie_name: str = "adi_session"
    csrf_cookie_name: str = "adi_csrf"

    session_lifetime_hours: int = Field(
        default=24,
        gt=0,
        le=720,
    )

    session_cookie_secure: bool = False

    session_cookie_samesite: Literal[
        "lax",
        "strict",
        "none",
    ] = "lax"

    session_cookie_path: str = "/"

    email_verification_token_lifetime_minutes: int = Field(
        default=1440,
        gt=0,
        le=10080,
    )

    password_reset_token_lifetime_minutes: int = Field(
        default=30,
        gt=0,
        le=1440,
    )

    password_min_length: int = Field(
        default=12,
        ge=8,
        le=128,
    )

    password_max_length: int = Field(
        default=128,
        ge=12,
        le=256,
    )

    csrf_protection_enabled: bool = True

    # Email / SMTP
    smtp_host: str | None = None

    smtp_port: int = Field(
        default=587,
        ge=1,
        le=65535,
    )

    smtp_username: str | None = None
    smtp_password: SecretStr = SecretStr("")
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str = "AI Document Intelligence Assistant"
    smtp_starttls: bool = True

    smtp_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=120,
    )

    # RAG / LLM
    rag_llm_provider: Literal[
        "mock",
        "ollama",
    ] = "mock"

    ollama_model: str = "qwen3:8b-q4_K_M"
    ollama_url: str = "http://localhost:11434"

    # PostgreSQL database
    postgres_host: str = "localhost"

    postgres_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
    )

    postgres_db: str = "ai_document_intelligence"
    postgres_user: str = "ai_document_app"
    postgres_password: SecretStr = SecretStr("")

    # Redis / Background Processing
    redis_url: SecretStr = SecretStr(
        "redis://127.0.0.1:6379/0"
    )

    # Document storage
    storage_backend: Literal["local"] = "local"

    upload_dir: Path = Path("uploads")
    sanitized_dir: Path = Path("data/private_storage/sanitized")

    max_file_size_mb: int = Field(
        default=50,
        gt=0,
    )

    # Vector database
    chroma_path: Path = Path("data/chroma")

    # Logging
    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    # --------------------------------------------------------
    # Path validation
    # --------------------------------------------------------

    @field_validator(
        "upload_dir",
        "sanitized_dir",
        "chroma_path",
    )
    @classmethod
    def resolve_backend_paths(
        cls,
        value: Path,
    ) -> Path:
        if value.is_absolute():
            return value.resolve()

        return (BACKEND_DIR / value).resolve()

    # --------------------------------------------------------
    # Redis URL validation
    # --------------------------------------------------------

    @staticmethod
    def validate_redis_url(
        redis_url: str,
        production: bool,
    ) -> None:
        try:
            parts = urlsplit(redis_url)
            port = parts.port
        except ValueError as exc:
            raise ValueError(
                "REDIS_URL contains an invalid port or URL"
            ) from exc

        if parts.scheme not in ("redis", "rediss"):
            raise ValueError(
                "REDIS_URL must use redis:// or rediss://"
            )

        if not parts.hostname:
            raise ValueError(
                "REDIS_URL must include a hostname"
            )

        if port is not None and not (1 <= port <= 65535):
            raise ValueError(
                "REDIS_URL port must be between 1 and 65535"
            )

        if production:
            if parts.scheme != "rediss":
                raise ValueError(
                    "Production Redis must use TLS with a rediss:// URL"
                )

            if not parts.username or not parts.password:
                raise ValueError(
                    "Production Redis must configure an ACL username and password"
                )

    # --------------------------------------------------------
    # Environment validation
    # --------------------------------------------------------

    @model_validator(mode="after")
    def validate_environment(self):
        if self.app_env == "production" and self.debug:
            raise ValueError(
                "DEBUG must be false in production"
            )

        if (
            self.app_env == "production"
            and self.storage_backend == "local"
        ):
            raise ValueError(
                "Local document storage is not allowed in production. "
                "Configure a secure cloud storage backend."
            )

        if (
            self.app_env == "production"
            and not self.session_cookie_secure
        ):
            raise ValueError(
                "SESSION_COOKIE_SECURE must be true in production"
            )

        if (
            self.session_cookie_samesite == "none"
            and not self.session_cookie_secure
        ):
            raise ValueError(
                "SESSION_COOKIE_SECURE must be true when "
                "SESSION_COOKIE_SAMESITE is none"
            )

        if self.password_min_length > self.password_max_length:
            raise ValueError(
                "PASSWORD_MIN_LENGTH cannot exceed PASSWORD_MAX_LENGTH"
            )

        if self.smtp_host:
            if not self.smtp_from_email:
                raise ValueError(
                    "SMTP_FROM_EMAIL is required when SMTP_HOST is configured"
                )

            if not self.smtp_starttls:
                raise ValueError(
                    "SMTP_STARTTLS must be true when SMTP is configured"
                )

        if bool(self.smtp_username) != bool(
            self.smtp_password.get_secret_value()
        ):
            raise ValueError(
                "SMTP_USERNAME and SMTP_PASSWORD must be configured together"
            )

        self.validate_redis_url(
            self.redis_url.get_secret_value(),
            production=self.app_env == "production",
        )

        return self


# ------------------------------------------------------------
# Shared settings instance
# ------------------------------------------------------------

settings = Settings()
