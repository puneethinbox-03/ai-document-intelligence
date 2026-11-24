from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models import UserSession
from app.services.auth import logout_service
from app.services.auth.logout_service import revoke_session


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def active_session():
    return UserSession(
        token_hash="hashed-session-token",
        expires_at=datetime.now(timezone.utc),
    )


def mock_hash_token(monkeypatch):
    monkeypatch.setattr(
        logout_service,
        "hash_token",
        lambda raw_token: "hashed-session-token",
    )


def test_revoke_session_revokes_active_session(
    mock_db,
    active_session,
    monkeypatch,
):
    mock_db.scalar.return_value = active_session
    mock_hash_token(monkeypatch)

    result = revoke_session(
        mock_db,
        raw_token="raw-session-token",
    )

    assert result is True
    assert active_session.revoked_at is not None

    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_revoke_session_rejects_empty_token(mock_db):
    result = revoke_session(mock_db, raw_token="")

    assert result is False
    mock_db.scalar.assert_not_called()
    mock_db.commit.assert_not_called()


def test_revoke_session_handles_unknown_token(
    mock_db,
    monkeypatch,
):
    mock_db.scalar.return_value = None
    mock_hash_token(monkeypatch)

    result = revoke_session(
        mock_db,
        raw_token="unknown-session-token",
    )

    assert result is False
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_revoke_session_does_not_revoke_twice(
    mock_db,
    active_session,
    monkeypatch,
):
    existing_revocation_time = datetime.now(timezone.utc)
    active_session.revoked_at = existing_revocation_time
    mock_db.scalar.return_value = active_session
    mock_hash_token(monkeypatch)

    result = revoke_session(
        mock_db,
        raw_token="raw-session-token",
    )

    assert result is False
    assert active_session.revoked_at == existing_revocation_time
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()


def test_revoke_session_rolls_back_on_database_failure(
    mock_db,
    active_session,
    monkeypatch,
):
    mock_db.scalar.return_value = active_session
    mock_db.commit.side_effect = RuntimeError("Database failure")
    mock_hash_token(monkeypatch)

    with pytest.raises(RuntimeError, match="Database failure"):
        revoke_session(
            mock_db,
            raw_token="raw-session-token",
        )

    assert active_session.revoked_at is not None
    mock_db.rollback.assert_called_once()
