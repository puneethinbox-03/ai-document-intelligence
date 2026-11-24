import smtplib
from email import message_from_string
from email.policy import default
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from app.services.auth import email_service
from app.services.auth.email_service import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)


@pytest.fixture
def configured_smtp(monkeypatch):
    """Configure test SMTP settings without changing the .env file."""

    monkeypatch.setattr(
        email_service.settings,
        "smtp_host",
        "smtp.example.com",
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_port",
        587,
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_username",
        "test-user",
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_password",
        SecretStr("test-password"),
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_from_email",
        "no-reply@example.com",
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_from_name",
        "Test Application",
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_starttls",
        True,
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_timeout_seconds",
        10.0,
    )
    monkeypatch.setattr(
        email_service.settings,
        "frontend_url",
        "http://localhost:3000",
    )

    smtp_server = MagicMock()
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp_server

    return smtp_server, smtp_context


def test_verification_email_contains_correct_link(configured_smtp):
    smtp_server, smtp_context = configured_smtp

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ) as smtp_factory:
        send_verification_email(
            recipient="user@example.com",
            token="verification-token",
        )

    smtp_factory.assert_called_once_with(
        host="smtp.example.com",
        port=587,
        timeout=10.0,
    )

    smtp_server.send_message.assert_called_once()

    message = smtp_server.send_message.call_args.args[0]

    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Verify your email address"
    assert "no-reply@example.com" in message["From"]
    assert (
        "http://localhost:3000/verify-email?token=verification-token"
        in message.get_content()
    )


def test_password_reset_email_contains_correct_link(configured_smtp):
    smtp_server, smtp_context = configured_smtp

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        send_password_reset_email(
            recipient="user@example.com",
            token="reset-token",
        )

    message = smtp_server.send_message.call_args.args[0]

    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Reset your password"
    assert (
        "http://localhost:3000/reset-password?token=reset-token"
        in message.get_content()
    )


def test_smtp_uses_starttls_and_authentication(configured_smtp):
    smtp_server, smtp_context = configured_smtp

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        send_verification_email(
            recipient="user@example.com",
            token="test-token",
        )

    smtp_server.ehlo.assert_called()
    smtp_server.starttls.assert_called_once()
    smtp_server.login.assert_called_once_with(
        "test-user",
        "test-password",
    )
    smtp_server.send_message.assert_called_once()


def test_email_delivery_fails_when_smtp_is_not_configured(monkeypatch):
    monkeypatch.setattr(
        email_service.settings,
        "smtp_host",
        None,
    )
    monkeypatch.setattr(
        email_service.settings,
        "smtp_from_email",
        None,
    )

    with pytest.raises(
        EmailDeliveryError,
        match="Email delivery is not configured",
    ):
        send_verification_email(
            recipient="user@example.com",
            token="test-token",
        )


def test_smtp_failure_raises_safe_email_delivery_error(configured_smtp):
    smtp_server, smtp_context = configured_smtp

    smtp_server.send_message.side_effect = smtplib.SMTPException(
        "Simulated SMTP failure"
    )

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        with pytest.raises(
            EmailDeliveryError,
            match="Unable to deliver email",
        ):
            send_verification_email(
                recipient="user@example.com",
                token="test-token",
            )


def test_verification_token_is_url_encoded(configured_smtp):
    smtp_server, smtp_context = configured_smtp

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        send_verification_email(
            recipient="user@example.com",
            token="token+/=",
        )

    message = smtp_server.send_message.call_args.args[0]

    assert "token=token%2B%2F%3D" in message.get_content()


def test_password_reset_token_is_url_encoded(configured_smtp):
    smtp_server, smtp_context = configured_smtp

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        send_password_reset_email(
            recipient="user@example.com",
            token="reset+/=",
        )

    message = smtp_server.send_message.call_args.args[0]

    assert "token=reset%2B%2F%3D" in message.get_content()


def test_smtp_failure_does_not_expose_credentials_or_token(
    configured_smtp,
):
    smtp_server, smtp_context = configured_smtp

    smtp_server.send_message.side_effect = smtplib.SMTPException(
        "Sensitive SMTP diagnostic"
    )

    with patch(
        "app.services.auth.email_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        with pytest.raises(EmailDeliveryError) as error:
            send_password_reset_email(
                recipient="user@example.com",
                token="private-reset-token",
            )

    assert "test-password" not in str(error.value)
    assert "private-reset-token" not in str(error.value)
    assert "Sensitive SMTP diagnostic" not in str(error.value)
