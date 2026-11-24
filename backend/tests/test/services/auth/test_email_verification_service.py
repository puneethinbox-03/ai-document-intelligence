from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models import EmailVerificationToken, User
from app.services.auth import email_verification_service
from app.services.auth.email_verification_service import (
    InvalidVerificationTokenError,
    verify_email,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def verification_data():
    user = User(
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="test-hash",
        is_active=True,
    )

    token = EmailVerificationToken(
        user=user,
        token_hash="hashed-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    return user, token


def test_verify_email_marks_user_verified_and_consumes_tokens(
    mock_db,
    verification_data,
    monkeypatch,
):
    user, token = verification_data
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        email_verification_service,
        "hash_token",
        lambda raw_token: "hashed-token",
    )

    result = verify_email(
        mock_db,
        raw_token="raw-verification-token",
    )

    assert result is user
    assert user.email_verified_at is not None
    assert token.used_at is not None
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_verify_email_rejects_unknown_token(mock_db, monkeypatch):
    mock_db.scalar.return_value = None

    monkeypatch.setattr(
        email_verification_service,
        "hash_token",
        lambda raw_token: "hashed-token",
    )

    with pytest.raises(InvalidVerificationTokenError):
        verify_email(mock_db, raw_token="unknown-token")

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


def test_verify_email_rejects_expired_token(
    mock_db,
    verification_data,
    monkeypatch,
):
    user, token = verification_data
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        email_verification_service,
        "hash_token",
        lambda raw_token: "hashed-token",
    )

    with pytest.raises(InvalidVerificationTokenError):
        verify_email(mock_db, raw_token="expired-token")

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()
    assert user.email_verified_at is None


def test_verify_email_rejects_already_used_token(
    mock_db,
    verification_data,
    monkeypatch,
):
    user, token = verification_data
    token.used_at = datetime.now(timezone.utc)
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        email_verification_service,
        "hash_token",
        lambda raw_token: "hashed-token",
    )

    with pytest.raises(InvalidVerificationTokenError):
        verify_email(mock_db, raw_token="used-token")

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()
    assert user.email_verified_at is None


def test_verify_email_rejects_inactive_user(
    mock_db,
    verification_data,
    monkeypatch,
):
    user, token = verification_data
    user.is_active = False
    mock_db.scalar.return_value = token

    monkeypatch.setattr(
        email_verification_service,
        "hash_token",
        lambda raw_token: "hashed-token",
    )

    with pytest.raises(InvalidVerificationTokenError):
        verify_email(mock_db, raw_token="inactive-user-token")

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


def test_verify_email_rolls_back_on_database_failure(
    mock_db,
    verification_data,
    monkeypatch,
):
    user, token = verification_data
    mock_db.scalar.return_value = token
    mock_db.commit.side_effect = RuntimeError("Database failure")

    monkeypatch.setattr(
        email_verification_service,
        "hash_token",
        lambda raw_token: "hashed-token",
    )

    with pytest.raises(RuntimeError, match="Database failure"):
        verify_email(mock_db, raw_token="raw-verification-token")

    mock_db.rollback.assert_called_once()
