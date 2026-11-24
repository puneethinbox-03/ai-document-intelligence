from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models import User, UserSession
from app.services.auth import session_service
from app.services.auth.session_service import (
    InvalidSessionError,
    get_authenticated_user,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def valid_session():
    user = User(
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="test-hash",
        email_verified_at=datetime.now(timezone.utc),
        is_active=True,
    )

    user_session = UserSession(
        user=user,
        token_hash="hashed-session-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        last_used_at=None,
    )

    return user, user_session


def mock_hash_token(monkeypatch):
    monkeypatch.setattr(
        session_service,
        "hash_token",
        lambda raw_token: "hashed-session-token",
    )


def test_get_authenticated_user_returns_user_and_updates_activity(
    mock_db,
    valid_session,
    monkeypatch,
):
    user, user_session = valid_session
    mock_db.scalar.return_value = user_session
    mock_hash_token(monkeypatch)

    result = get_authenticated_user(
        mock_db,
        raw_token="raw-session-token",
    )

    assert result is user
    assert user_session.last_used_at is not None

    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_get_authenticated_user_rejects_empty_token(mock_db):
    with pytest.raises(InvalidSessionError):
        get_authenticated_user(mock_db, raw_token="")

    mock_db.scalar.assert_not_called()
    mock_db.commit.assert_not_called()


def test_get_authenticated_user_rejects_unknown_session(
    mock_db,
    monkeypatch,
):
    mock_db.scalar.return_value = None
    mock_hash_token(monkeypatch)

    with pytest.raises(InvalidSessionError):
        get_authenticated_user(
            mock_db,
            raw_token="unknown-session-token",
        )

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


def test_get_authenticated_user_rejects_inactive_session_user(
    mock_db,
    valid_session,
    monkeypatch,
):
    user, user_session = valid_session
    user.is_active = False
    mock_db.scalar.return_value = user_session
    mock_hash_token(monkeypatch)

    with pytest.raises(InvalidSessionError):
        get_authenticated_user(
            mock_db,
            raw_token="raw-session-token",
        )

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


def test_get_authenticated_user_rejects_unverified_user(
    mock_db,
    valid_session,
    monkeypatch,
):
    user, user_session = valid_session
    user.email_verified_at = None
    mock_db.scalar.return_value = user_session
    mock_hash_token(monkeypatch)

    with pytest.raises(InvalidSessionError):
        get_authenticated_user(
            mock_db,
            raw_token="raw-session-token",
        )

    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()


def test_get_authenticated_user_rolls_back_on_database_failure(
    mock_db,
    valid_session,
    monkeypatch,
):
    user, user_session = valid_session
    mock_db.scalar.return_value = user_session
    mock_db.commit.side_effect = RuntimeError("Database failure")
    mock_hash_token(monkeypatch)

    with pytest.raises(RuntimeError, match="Database failure"):
        get_authenticated_user(
            mock_db,
            raw_token="raw-session-token",
        )

    mock_db.rollback.assert_called_once()
