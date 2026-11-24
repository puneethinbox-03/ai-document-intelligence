from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models import User, UserSession
from app.services.auth import login_service
from app.services.auth.login_service import (
    AuthenticationError,
    login_user,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def verified_user():
    return User(
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="test-password-hash",
        email_verified_at=datetime.now(timezone.utc),
        is_active=True,
    )


def mock_security_functions(monkeypatch):
    monkeypatch.setattr(
        login_service,
        "verify_password",
        lambda password, password_hash: (
            password == "CorrectPassword123!"
            and password_hash == "test-password-hash"
        ),
    )
    monkeypatch.setattr(
        login_service,
        "generate_secure_token",
        lambda: "raw-session-token",
    )
    monkeypatch.setattr(
        login_service,
        "hash_token",
        lambda token: "hashed-session-token",
    )


def test_login_user_creates_session(
    mock_db,
    verified_user,
    monkeypatch,
):
    mock_db.scalar.return_value = verified_user
    mock_security_functions(monkeypatch)

    result = login_user(
        mock_db,
        email="person@example.com",
        password="CorrectPassword123!",
    )

    assert result.user is verified_user
    assert result.session_token == "raw-session-token"
    assert result.expires_at > datetime.now(timezone.utc)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()

    created_session = mock_db.add.call_args.args[0]

    assert isinstance(created_session, UserSession)
    assert created_session.user is verified_user
    assert created_session.token_hash == "hashed-session-token"
    assert created_session.expires_at == result.expires_at
    assert created_session.last_used_at is not None


def test_login_user_normalizes_email(
    mock_db,
    verified_user,
    monkeypatch,
):
    mock_db.scalar.return_value = verified_user
    mock_security_functions(monkeypatch)

    login_user(
        mock_db,
        email="  PERSON@EXAMPLE.COM  ",
        password="CorrectPassword123!",
    )

    query = mock_db.scalar.call_args.args[0]
    compiled_query = str(query)

    assert "email_normalized" in compiled_query


def test_login_user_rejects_unknown_email(
    mock_db,
    monkeypatch,
):
    mock_db.scalar.return_value = None
    mock_security_functions(monkeypatch)

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        login_user(
            mock_db,
            email="unknown@example.com",
            password="CorrectPassword123!",
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_login_user_rejects_incorrect_password(
    mock_db,
    verified_user,
    monkeypatch,
):
    mock_db.scalar.return_value = verified_user
    mock_security_functions(monkeypatch)

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        login_user(
            mock_db,
            email="person@example.com",
            password="WrongPassword123!",
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_login_user_rejects_unverified_email(
    mock_db,
    verified_user,
    monkeypatch,
):
    verified_user.email_verified_at = None
    mock_db.scalar.return_value = verified_user
    mock_security_functions(monkeypatch)

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        login_user(
            mock_db,
            email="person@example.com",
            password="CorrectPassword123!",
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_login_user_rejects_inactive_account(
    mock_db,
    verified_user,
    monkeypatch,
):
    verified_user.is_active = False
    mock_db.scalar.return_value = verified_user
    mock_security_functions(monkeypatch)

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        login_user(
            mock_db,
            email="person@example.com",
            password="CorrectPassword123!",
        )

    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_login_user_rolls_back_on_database_failure(
    mock_db,
    verified_user,
    monkeypatch,
):
    mock_db.scalar.return_value = verified_user
    mock_db.commit.side_effect = RuntimeError("Database failure")
    mock_security_functions(monkeypatch)

    with pytest.raises(RuntimeError, match="Database failure"):
        login_user(
            mock_db,
            email="person@example.com",
            password="CorrectPassword123!",
        )

    mock_db.add.assert_called_once()
    mock_db.rollback.assert_called_once()
