from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings


class RegisterRequest(BaseModel):
    """Request body for creating a new user account."""

    email: EmailStr
    password: str
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot contain only whitespace")

        if len(value) < settings.password_min_length:
            raise ValueError(
                f"Password must contain at least "
                f"{settings.password_min_length} characters"
            )

        if len(value) > settings.password_max_length:
            raise ValueError(
                f"Password cannot exceed "
                f"{settings.password_max_length} characters"
            )

        return value


class LoginRequest(BaseModel):
    """Request body for authenticating an existing user."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class VerifyEmailRequest(BaseModel):
    """Request body for verifying an email address."""

    token: str = Field(min_length=1, max_length=256)


class PasswordResetRequest(BaseModel):
    """Request body for requesting a password-reset link."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Request body for completing a password reset."""

    token: str = Field(min_length=1, max_length=256)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot contain only whitespace")

        if len(value) < settings.password_min_length:
            raise ValueError(
                f"Password must contain at least "
                f"{settings.password_min_length} characters"
            )

        if len(value) > settings.password_max_length:
            raise ValueError(
                f"Password cannot exceed "
                f"{settings.password_max_length} characters"
            )

        return value


class UserResponse(BaseModel):
    """Public user information. Never expose credentials or token hashes."""

    id: UUID
    email: EmailStr
    display_name: str | None
    email_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """Authentication response. Session credentials use an HttpOnly cookie."""

    user: UserResponse


class MessageResponse(BaseModel):
    """Generic API message response."""

    message: str
