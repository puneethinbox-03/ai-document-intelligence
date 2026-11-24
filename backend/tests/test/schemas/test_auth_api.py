import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
    VerifyEmailRequest,
)


def test_verify_email_request_accepts_token():
    request = VerifyEmailRequest(token="valid-verification-token")

    assert request.token == "valid-verification-token"


def test_verify_email_request_rejects_empty_token():
    with pytest.raises(ValidationError):
        VerifyEmailRequest(token="")


def test_password_reset_request_accepts_valid_email():
    request = PasswordResetRequest(email="person@example.com")

    assert request.email == "person@example.com"


def test_password_reset_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        PasswordResetRequest(email="invalid-email")


def test_password_reset_confirm_accepts_valid_password():
    request = PasswordResetConfirmRequest(
        token="valid-reset-token",
        new_password="NewSecurePassword123!",
    )

    assert request.new_password == "NewSecurePassword123!"


def test_password_reset_confirm_rejects_short_password():
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(
            token="valid-reset-token",
            new_password="short",
        )


def test_password_reset_confirm_rejects_whitespace_password():
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(
            token="valid-reset-token",
            new_password=" " * 20,
        )


def test_password_reset_confirm_preserves_password():
    password = "  ValidPassword123!  "

    request = PasswordResetConfirmRequest(
        token="valid-reset-token",
        new_password=password,
    )

    assert request.new_password == password


def test_password_reset_confirm_rejects_empty_token():
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(
            token="",
            new_password="NewSecurePassword123!",
        )


def test_message_response_contains_only_message():
    response = MessageResponse(message="Request received")

    assert response.model_dump() == {
        "message": "Request received"
    }


def test_auth_response_contains_public_user_fields_only():
    from datetime import datetime, timezone
    from uuid import uuid4

    user = UserResponse(
        id=uuid4(),
        email="person@example.com",
        display_name="Person",
        email_verified=True,
        created_at=datetime.now(timezone.utc),
    )

    response = AuthResponse(user=user)

    assert "password_hash" not in response.model_dump()
    assert "session_token" not in response.model_dump()
    assert response.user.email == "person@example.com"


def test_registration_and_login_schemas_remain_available():
    registration = RegisterRequest(
        email="person@example.com",
        password="SecurePassword123!",
    )

    login = LoginRequest(
        email="person@example.com",
        password="old",
    )

    assert registration.email == "person@example.com"
    assert login.password == "old"
