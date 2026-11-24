from sqlalchemy import DateTime, String

from app.models.base import Base
from app.models.auth_token import (
    EmailVerificationToken,
    PasswordResetToken,
)


def test_auth_token_models_use_shared_metadata():
    """Verify both token models use shared application metadata."""

    assert EmailVerificationToken.metadata is Base.metadata
    assert PasswordResetToken.metadata is Base.metadata

    assert EmailVerificationToken.__tablename__ == "email_verification_tokens"
    assert PasswordResetToken.__tablename__ == "password_reset_tokens"


def test_email_verification_token_has_expected_columns():
    """Verify email verification token columns."""

    expected_columns = {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "used_at",
        "created_at",
        "updated_at",
    }

    actual_columns = set(
        EmailVerificationToken.__table__.columns.keys()
    )

    assert expected_columns.issubset(actual_columns)


def test_password_reset_token_has_expected_columns():
    """Verify password reset token columns."""

    expected_columns = {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "used_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }

    actual_columns = set(
        PasswordResetToken.__table__.columns.keys()
    )

    assert expected_columns.issubset(actual_columns)


def test_auth_token_user_foreign_keys():
    """Verify both token models reference users.id."""

    for model in (EmailVerificationToken, PasswordResetToken):
        column = model.__table__.c.user_id

        assert column.nullable is False
        assert len(column.foreign_keys) == 1

        foreign_key = next(iter(column.foreign_keys))

        assert foreign_key.target_fullname == "users.id"


def test_auth_token_hash_configuration():
    """Verify token hashes are stored as bounded strings."""

    for model in (EmailVerificationToken, PasswordResetToken):
        column = model.__table__.c.token_hash

        assert isinstance(column.type, String)
        assert column.type.length == 64
        assert column.nullable is False


def test_auth_token_timestamp_configuration():
    """Verify expiry and usage timestamps are timezone-aware."""

    for model in (EmailVerificationToken, PasswordResetToken):
        table = model.__table__

        assert isinstance(table.c.expires_at.type, DateTime)
        assert table.c.expires_at.type.timezone is True
        assert table.c.expires_at.nullable is False

        assert table.c.used_at.type.timezone is True
        assert table.c.used_at.nullable is True


def test_password_reset_token_revocation_timestamp():
    """Verify password reset tokens support revocation."""

    column = PasswordResetToken.__table__.c.revoked_at

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is True
