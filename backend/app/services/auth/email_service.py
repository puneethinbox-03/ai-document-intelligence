import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings


class EmailDeliveryError(Exception):
    """Raised when an email cannot be delivered."""


def _send_email(
    *,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """
    Send a plain-text email using configured SMTP settings.

    SMTP credentials and email tokens must never be logged.
    """

    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailDeliveryError(
            "Email delivery is not configured"
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    )
    message["To"] = recipient
    message.set_content(body)

    try:
        context = ssl.create_default_context()

        with smtplib.SMTP(
            host=settings.smtp_host,
            port=settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as server:

            server.ehlo()

            if settings.smtp_starttls:
                server.starttls(context=context)
                server.ehlo()

            if settings.smtp_username:
                server.login(
                    settings.smtp_username,
                    settings.smtp_password.get_secret_value(),
                )

            server.send_message(message)

    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        raise EmailDeliveryError(
            "Unable to deliver email"
        ) from exc


def send_verification_email(
    *,
    recipient: str,
    token: str,
) -> None:
    """Send an account email-verification link."""

    query = urlencode({"token": token})

    verification_url = (
        f"{settings.frontend_url.rstrip('/')}"
        f"/verify-email?{query}"
    )

    body = (
        "Hello,\n\n"
        "Thank you for registering with "
        "AI Document Intelligence Assistant.\n\n"
        "Please verify your email address using this link:\n"
        f"{verification_url}\n\n"
        f"This link expires in "
        f"{settings.email_verification_token_lifetime_minutes} minutes.\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )

    _send_email(
        recipient=recipient,
        subject="Verify your email address",
        body=body,
    )


def send_password_reset_email(
    *,
    recipient: str,
    token: str,
) -> None:
    """Send a password-reset link."""

    query = urlencode({"token": token})

    reset_url = (
        f"{settings.frontend_url.rstrip('/')}"
        f"/reset-password?{query}"
    )

    body = (
        "Hello,\n\n"
        "A password-reset request was received for your account.\n\n"
        "Use the following link to reset your password:\n"
        f"{reset_url}\n\n"
        f"This link expires in "
        f"{settings.password_reset_token_lifetime_minutes} minutes.\n\n"
        "If you did not request a password reset, "
        "you can ignore this email.\n"
    )

    _send_email(
        recipient=recipient,
        subject="Reset your password",
        body=body,
    )
