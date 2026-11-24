from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models import User
from app.services.auth.resend_verification_service import (
    resend_verification_email,
)


def make_user(
    *,
    email_verified_at=None,
    is_active=True,
):
    return User(
        id=uuid4(),
        email="user@example.com",
        email_normalized="user@example.com",
        password_hash="test-password-hash",
        email_verified_at=email_verified_at,
        is_active=is_active,
    )


def test_resend_creates_replacement_token():
    db = MagicMock()
    db.scalar.return_value = make_user()

    result = resend_verification_email(
        db,
        email="USER@example.com",
    )

    assert result is not None
    assert isinstance(result.verification_token, str)
    assert len(result.verification_token) > 20
    db.execute.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_resend_normalizes_email():
    db = MagicMock()
    db.scalar.return_value = make_user()

    resend_verification_email(
        db,
        email="  USER@EXAMPLE.COM  ",
    )

    query = db.scalar.call_args.args[0]
    compiled_query = query.compile()

    assert "email_normalized" in str(compiled_query)
    assert "user@example.com" in compiled_query.params.values()


def test_resend_returns_none_for_unknown_user():
    db = MagicMock()
    db.scalar.return_value = None

    result = resend_verification_email(
        db,
        email="unknown@example.com",
    )

    assert result is None
    db.rollback.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_resend_returns_none_for_verified_user():
    db = MagicMock()
    db.scalar.return_value = make_user(
        email_verified_at=datetime.now(timezone.utc)
    )

    result = resend_verification_email(
        db,
        email="user@example.com",
    )

    assert result is None
    db.rollback.assert_called_once()
    db.add.assert_not_called()


def test_resend_returns_none_for_inactive_user():
    db = MagicMock()
    db.scalar.return_value = make_user(is_active=False)

    result = resend_verification_email(
        db,
        email="user@example.com",
    )

    assert result is None
    db.rollback.assert_called_once()
    db.add.assert_not_called()


def test_resend_rolls_back_on_database_failure():
    db = MagicMock()
    db.scalar.return_value = make_user()
    db.execute.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError):
        resend_verification_email(
            db,
            email="user@example.com",
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
