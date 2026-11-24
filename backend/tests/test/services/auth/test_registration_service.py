from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.auth_token import EmailVerificationToken
from app.models.user import User
from app.services.auth import registration_service
from app.services.auth.registration_service import (
    EmailAlreadyRegisteredError,
    register_user,
)


@pytest.fixture
def mock_db():
    return MagicMock()


def test_register_user_creates_unverified_user_and_token(
    mock_db,
    monkeypatch,
):
    monkeypatch.setattr(
        registration_service,
        "hash_password",
        lambda password: "argon2-test-hash",
    )
    monkeypatch.setattr(
        registration_service,
        "generate_secure_token",
        lambda: "raw-verification-token",
    )
    monkeypatch.setattr(
        registration_service,
        "hash_token",
        lambda token: "hashed-verification-token",
    )

    mock_db.scalar.return_value = None

    result = register_user(
        mock_db,
        email="Person@Example.com",
        password="StrongPassword123!",
        display_name="Test User",
    )

    assert isinstance(result.user, User)
    assert result.user.email == "Person@Example.com"
    assert result.user.email_normalized == "person@example.com"
    assert result.user.password_hash == "argon2-test-hash"
    assert result.user.display_name == "Test User"
    assert result.user.email_verified_at is None

    assert result.verification_token == "raw-verification-token"

    mock_db.add.assert_any_call(result.user)

    token_record = next(
        call.args[0]
        for call in mock_db.add.call_args_list
        if isinstance(call.args[0], EmailVerificationToken)
    )

    assert token_record.user is result.user
    assert token_record.token_hash == "hashed-verification-token"
    assert token_record.expires_at > datetime.now(timezone.utc)

    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_register_user_normalizes_email_and_display_name(
    mock_db,
    monkeypatch,
):
    monkeypatch.setattr(
        registration_service,
        "hash_password",
        lambda password: "test-hash",
    )
    monkeypatch.setattr(
        registration_service,
        "generate_secure_token",
        lambda: "test-token",
    )
    monkeypatch.setattr(
        registration_service,
        "hash_token",
        lambda token: "test-token-hash",
    )

    mock_db.scalar.return_value = None

    result = register_user(
        mock_db,
        email="  PERSON@EXAMPLE.COM  ",
        password="StrongPassword123!",
        display_name="  Test User  ",
    )

    assert result.user.email_normalized == "person@example.com"
    assert result.user.display_name == "Test User"


def test_register_user_converts_blank_display_name_to_none(
    mock_db,
    monkeypatch,
):
    monkeypatch.setattr(
        registration_service,
        "hash_password",
        lambda password: "test-hash",
    )
    monkeypatch.setattr(
        registration_service,
        "generate_secure_token",
        lambda: "test-token",
    )
    monkeypatch.setattr(
        registration_service,
        "hash_token",
        lambda token: "test-token-hash",
    )

    mock_db.scalar.return_value = None

    result = register_user(
        mock_db,
        email="person@example.com",
        password="StrongPassword123!",
        display_name="   ",
    )

    assert result.user.display_name is None


def test_register_user_rejects_existing_email(mock_db):
    existing_user = User(
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="existing-hash",
    )

    mock_db.scalar.return_value = existing_user

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(
            mock_db,
            email="person@example.com",
            password="StrongPassword123!",
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_not_called()


def test_register_user_handles_concurrent_duplicate_registration(
    mock_db,
    monkeypatch,
):
    monkeypatch.setattr(
        registration_service,
        "hash_password",
        lambda password: "test-hash",
    )
    monkeypatch.setattr(
        registration_service,
        "generate_secure_token",
        lambda: "test-token",
    )
    monkeypatch.setattr(
        registration_service,
        "hash_token",
        lambda token: "test-token-hash",
    )

    existing_user = User(
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="existing-hash",
    )

    mock_db.scalar.side_effect = [
        None,
        existing_user,
    ]

    mock_db.flush.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("Unique constraint violation"),
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(
            mock_db,
            email="person@example.com",
            password="StrongPassword123!",
        )

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


def test_register_user_rolls_back_on_unexpected_failure(
    mock_db,
    monkeypatch,
):
    monkeypatch.setattr(
        registration_service,
        "hash_password",
        lambda password: "test-hash",
    )
    monkeypatch.setattr(
        registration_service,
        "generate_secure_token",
        lambda: "test-token",
    )
    monkeypatch.setattr(
        registration_service,
        "hash_token",
        lambda token: "test-token-hash",
    )

    mock_db.scalar.return_value = None
    mock_db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        register_user(
            mock_db,
            email="person@example.com",
            password="StrongPassword123!",
        )

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_called_once()
