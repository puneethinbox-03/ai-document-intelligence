
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ------------------------------------------------------------
# Backend directory
# ------------------------------------------------------------

# config.py is located inside:
# backend/app/core/config.py
#
# parents[0] = backend/app/core
# parents[1] = backend/app
# parents[2] = backend

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

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    app_name: str = "AI Document Intelligence Assistant"

    app_version: str = "0.1.0"

    app_env: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    debug: bool = True

    api_prefix: str = "/api"

    # --------------------------------------------------------
    # CORS
    # --------------------------------------------------------

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # --------------------------------------------------------
    # RAG / LLM
    # --------------------------------------------------------

    rag_llm_provider: Literal[
        "mock",
        "ollama",
    ] = "mock"

    ollama_model: str = "qwen3:8b-q4_K_M"

    ollama_url: str = "http://localhost:11434"

    # --------------------------------------------------------
    # Document storage
    # --------------------------------------------------------

    upload_dir: Path = Path("uploads")

    max_file_size_mb: int = Field(
        default=50,
        gt=0,
    )

    # --------------------------------------------------------
    # Vector database
    # --------------------------------------------------------

    chroma_path: Path = Path("data/chroma")

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

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
        "chroma_path",
    )
    @classmethod
    def resolve_backend_paths(
        cls,
        value: Path,
    ) -> Path:
        """
        Resolve relative storage paths against backend/.

        This keeps storage locations consistent even when
        the application is started from a different directory.
        """

        if value.is_absolute():
            return value.resolve()

        return (BACKEND_DIR / value).resolve()

    # --------------------------------------------------------
    # Environment validation
    # --------------------------------------------------------

    @model_validator(mode="after")
    def validate_environment(self):
        """
        Prevent production from accidentally running
        with development debug mode enabled.
        """

        if self.app_env == "production" and self.debug:
            raise ValueError(
                "DEBUG must be false in production"
            )

        return self


# ------------------------------------------------------------
# Shared settings instance
# ------------------------------------------------------------

settings = Settings()
