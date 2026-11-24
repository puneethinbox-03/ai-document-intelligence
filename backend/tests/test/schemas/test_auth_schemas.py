from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)


def test_register_request_accepts_valid_data():
    request = RegisterRequest(
        email="person@example.com",
        password="StrongPassword123!",
        display_name="Test User",
    )

    assert str(request.email) == "person@example.com"
    assert request.password == "StrongPassword123!"
    assert request.display_name == "Test User"


def test_register_request_accepts_optional_display_name():
    request = RegisterRequest(
        email="person@example.com",
        password="StrongPassword123!",
    )

    assert request.display_name is None


def test_register_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="not-an-email",
            password="StrongPassword123!",
        )


def test_register_request_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password="Short123!",
        )


def test_register_request_rejects_long_password():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password="A" * 129,
        )


def test_register_request_rejects_whitespace_only_password():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password=" " * 12,
        )


def test_register_request_preserves_password_exactly():
    password = "  StrongPassword123!  "

    request = RegisterRequest(
        email="person@example.com",
        password=password,
    )

    assert request.password == password


def test_register_request_rejects_long_display_name():
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password="StrongPassword123!",
            display_name="A" * 101,
        )


def test_login_request_accepts_valid_credentials():
    request = LoginRequest(
        email="person@example.com",
        password="ExistingPassword123!",
    )

    assert str(request.email) == "person@example.com"
    assert request.password == "ExistingPassword123!"


def test_login_request_does_not_apply_registration_minimum():
    request = LoginRequest(
        email="person@example.com",
        password="OldPass1!",
    )

    assert request.password == "OldPass1!"


def test_login_request_rejects_empty_password():
    with pytest.raises(ValidationError):
        LoginRequest(
            email="person@example.com",
            password="",
        )


def test_user_response_contains_public_fields():
    user_id = uuid4()
    created_at = datetime.now(timezone.utc)

    response = UserResponse(
        id=user_id,
        email="person@example.com",
        display_name="Test User",
        email_verified=True,
        created_at=created_at,
    )

    assert response.id == user_id
    assert response.email == "person@example.com"
    assert response.display_name == "Test User"
    assert response.email_verified is True
    assert response.created_at == created_at

    assert "password_hash" not in response.model_dump()
    assert "token_hash" not in response.model_dump()


def test_auth_response_contains_user():
    user = UserResponse(
        id=uuid4(),
        email="person@example.com",
        display_name="Test User",
        email_verified=False,
        created_at=datetime.now(timezone.utc),
    )

    response = AuthResponse(user=user)

    assert response.user == user
    assert "session_token" not in response.model_dump()
