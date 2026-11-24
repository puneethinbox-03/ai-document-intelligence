from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models import PasswordResetToken, User
from app.services.auth import password_reset_service
from app.services.auth.password_reset_service import (
    InvalidPasswordResetTokenError,
    request_password_reset,
    reset_password,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def active_user():
    return User(
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="old-password-hash",
        is_active=True,
    )


@pytest.fixture
def valid_reset_data(active_user):
    token = PasswordResetToken(
        user=active_user,
        token_hash="hashed-reset-token",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
    )
    return active_user, token


def mock_token_functions(monkeypatch):
    monkeypatch.setattr(
        password_reset_service,
        "generate_secure_token",
        lambda: "raw-reset-token",
    )
    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )


def test_request_password_reset_creates_token(
    mock_db,
    active_user,
    monkeypatch,
):
    mock_db.scalar.return_value = active_user
    mock_token_functions(monkeypatch)

    result = request_password_reset(
        mock_db,
        email="person@example.com",
    )

    assert result is not None
    assert result.reset_token == "raw-reset-token"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()

    created_token = mock_db.add.call_args.args[0]

    assert isinstance(created_token, PasswordResetToken)
    assert created_token.user is active_user
    assert created_token.token_hash == "hashed-reset-token"
    assert created_token.expires_at > datetime.now(timezone.utc)


def test_request_password_reset_normalizes_email(
    mock_db,
    active_user,
    monkeypatch,
):
    mock_db.scalar.return_value = active_user
    mock_token_functions(monkeypatch)

    request_password_reset(
        mock_db,
        email="  PERSON@EXAMPLE.COM  ",
    )

    query = mock_db.scalar.call_args.args[0]

    assert "email_normalized" in str(query)


def test_request_password_reset_returns_none_for_unknown_email(
    mock_db,
    monkeypatch,
):
    mock_db.scalar.return_value = None
    mock_token_functions(monkeypatch)

    result = request_password_reset(
        mock_db,
        email="unknown@example.com",
    )

    assert result is None
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


def test_request_password_reset_rolls_back_on_database_failure(
    mock_db,
    active_user,
    monkeypatch,
):
    mock_db.scalar.return_value = active_user
    mock_db.commit.side_effect = RuntimeError("Database failure")
    mock_token_functions(monkeypatch)

    with pytest.raises(RuntimeError, match="Database failure"):
        request_password_reset(
            mock_db,
            email="person@example.com",
        )

    mock_db.rollback.assert_called_once()


def test_reset_password_updates_password_and_consumes_token(
    mock_db,
    valid_reset_data,
    monkeypatch,
):
    user, token = valid_reset_data
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )
    monkeypatch.setattr(
        password_reset_service,
        "hash_password",
        lambda password: "new-argon2-password-hash",
    )

    result = reset_password(
        mock_db,
        raw_token="raw-reset-token",
        new_password="NewSecurePassword123!",
    )

    assert result is user
    assert user.password_hash == "new-argon2-password-hash"
    assert token.used_at is not None

    assert mock_db.execute.call_count == 2
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_reset_password_rejects_unknown_token(
    mock_db,
    monkeypatch,
):
    mock_db.scalar.return_value = None

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            mock_db,
            raw_token="unknown-token",
            new_password="NewSecurePassword123!",
        )

    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_reset_password_rejects_expired_token(
    mock_db,
    valid_reset_data,
    monkeypatch,
):
    user, token = valid_reset_data
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            mock_db,
            raw_token="expired-token",
            new_password="NewSecurePassword123!",
        )

    assert user.password_hash == "old-password-hash"
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_reset_password_rejects_used_token(
    mock_db,
    valid_reset_data,
    monkeypatch,
):
    user, token = valid_reset_data
    token.used_at = datetime.now(timezone.utc)
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            mock_db,
            raw_token="used-token",
            new_password="NewSecurePassword123!",
        )

    assert user.password_hash == "old-password-hash"
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_reset_password_rejects_revoked_token(
    mock_db,
    valid_reset_data,
    monkeypatch,
):
    user, token = valid_reset_data
    token.revoked_at = datetime.now(timezone.utc)
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            mock_db,
            raw_token="revoked-token",
            new_password="NewSecurePassword123!",
        )

    assert user.password_hash == "old-password-hash"
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_reset_password_rejects_inactive_user(
    mock_db,
    valid_reset_data,
    monkeypatch,
):
    user, token = valid_reset_data
    user.is_active = False
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            mock_db,
            raw_token="inactive-user-token",
            new_password="NewSecurePassword123!",
        )

    assert user.password_hash == "old-password-hash"
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_reset_password_rolls_back_on_database_failure(
    mock_db,
    valid_reset_data,
    monkeypatch,
):
    user, token = valid_reset_data
    mock_db.scalar.return_value = token
    mock_db.commit.side_effect = RuntimeError("Database failure")

    monkeypatch.setattr(
        password_reset_service,
        "hash_token",
        lambda raw_token: "hashed-reset-token",
    )
    monkeypatch.setattr(
        password_reset_service,
        "hash_password",
        lambda password: "new-argon2-password-hash",
    )

    with pytest.raises(RuntimeError, match="Database failure"):
        reset_password(
            mock_db,
            raw_token="raw-reset-token",
            new_password="NewSecurePassword123!",
        )

    mock_db.rollback.assert_called_once()
