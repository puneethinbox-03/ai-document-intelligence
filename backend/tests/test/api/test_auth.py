from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models import User


@pytest.fixture
def client():
    """
    Create an API test client with an overridden database dependency.

    Authentication API tests mock service operations and do not
    write to the development PostgreSQL database.
    """

    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def create_verified_user():
    """Create an in-memory verified user for API response tests."""

    now = datetime.now(timezone.utc)

    return User(
        id=uuid4(),
        email="person@example.com",
        email_normalized="person@example.com",
        password_hash="test-password-hash",
        display_name="Test Person",
        email_verified_at=now,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def get_csrf_headers(client):
    """
    Request a CSRF token and prepare headers for a protected POST.
    """

    response = client.get("/api/auth/csrf")

    assert response.status_code == 200

    csrf_token = response.json()["csrf_token"]

    assert csrf_token
    assert client.cookies.get(settings.csrf_cookie_name) == csrf_token

    return {
        "Origin": settings.frontend_url,
        "X-CSRF-Token": csrf_token,
    }


def test_csrf_endpoint_issues_token_and_cookie(client):
    response = client.get("/api/auth/csrf")

    assert response.status_code == 200

    data = response.json()

    assert "csrf_token" in data
    assert data["csrf_token"]

    assert (
        client.cookies.get(settings.csrf_cookie_name)
        == data["csrf_token"]
    )

    cookie_headers = response.headers.get_list("set-cookie")

    csrf_cookie_header = next(
        header
        for header in cookie_headers
        if header.startswith(settings.csrf_cookie_name + "=")
    )

    assert "httponly" not in csrf_cookie_header.lower()
    assert "samesite=lax" in csrf_cookie_header.lower()


def test_login_rejects_request_without_csrf(client, monkeypatch):
    login_called = False

    def mock_login_user(*args, **kwargs):
        nonlocal login_called
        login_called = True

    monkeypatch.setattr(
        auth_api,
        "login_user",
        mock_login_user,
    )

    response = client.post(
        "/api/auth/login",
        headers={
            "Origin": settings.frontend_url,
        },
        json={
            "email": "person@example.com",
            "password": "CorrectPassword123!",
        },
    )

    assert response.status_code == 403
    assert login_called is False


def test_login_creates_http_only_session_cookie(
    client,
    monkeypatch,
):
    user = create_verified_user()

    monkeypatch.setattr(
        auth_api,
        "login_user",
        lambda db, email, password: SimpleNamespace(
            user=user,
            session_token="test-raw-session-token",
        ),
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "email": "person@example.com",
            "password": "CorrectPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user"]["email"] == "person@example.com"
    assert data["user"]["display_name"] == "Test Person"
    assert data["user"]["email_verified"] is True

    # The raw session token must never appear in the JSON response.
    assert "session_token" not in data
    assert "test-raw-session-token" not in response.text

    # The session token must be stored in the HttpOnly cookie.
    assert (
        client.cookies.get(settings.session_cookie_name)
        == "test-raw-session-token"
    )

    cookie_headers = response.headers.get_list("set-cookie")

    session_cookie_header = next(
        header
        for header in cookie_headers
        if header.startswith(settings.session_cookie_name + "=")
    )

    assert "httponly" in session_cookie_header.lower()
    assert "samesite=lax" in session_cookie_header.lower()
    assert "path=/" in session_cookie_header.lower()


def test_me_returns_current_user_profile(client):
    user = create_verified_user()

    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/api/auth/me")

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "person@example.com"
    assert data["display_name"] == "Test Person"
    assert data["email_verified"] is True

    # Private authentication fields must not be returned.
    assert "password_hash" not in data
    assert "session_token" not in data


def test_registration_does_not_expose_verification_token(
    client,
    monkeypatch,
):
    user = create_verified_user()
    sent_emails = []

    monkeypatch.setattr(
        auth_api,
        "register_user",
        lambda db, email, password, display_name: SimpleNamespace(
            user=user,
            verification_token="private-verification-token",
        ),
    )

    monkeypatch.setattr(
        auth_api,
        "send_verification_email",
        lambda recipient, token: sent_emails.append((recipient, token)),
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "email": "person@example.com",
            "password": "StrongPassword123!",
            "display_name": "Test Person",
        },
    )

    assert response.status_code == 202
    assert response.json()["message"] == auth_api.GENERIC_REGISTRATION_MESSAGE

    assert "private-verification-token" not in response.text
    assert sent_emails == [
        ("person@example.com", "private-verification-token")
    ]


def test_duplicate_registration_returns_generic_response(
    client,
    monkeypatch,
):
    def reject_duplicate(*args, **kwargs):
        raise auth_api.EmailAlreadyRegisteredError()

    monkeypatch.setattr(
        auth_api,
        "register_user",
        reject_duplicate,
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/register",
        headers=headers,
        json={
            "email": "existing@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": auth_api.GENERIC_REGISTRATION_MESSAGE
    }


def test_email_verification_passes_token_to_service(
    client,
    monkeypatch,
):
    verified_tokens = []

    monkeypatch.setattr(
        auth_api,
        "verify_email",
        lambda db, raw_token: verified_tokens.append(raw_token),
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/verify-email",
        headers=headers,
        json={
            "token": "test-verification-token",
        },
    )

    assert response.status_code == 200
    assert verified_tokens == ["test-verification-token"]


def test_password_reset_request_returns_generic_response(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        auth_api,
        "request_password_reset",
        lambda db, email: None,
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/password-reset/request",
        headers=headers,
        json={
            "email": "unknown@example.com",
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": auth_api.GENERIC_PASSWORD_RESET_MESSAGE
    }


def test_logout_revokes_session_and_clears_auth_cookies(
    client,
    monkeypatch,
):
    revoked_tokens = []

    monkeypatch.setattr(
        auth_api,
        "revoke_session",
        lambda db, raw_token: revoked_tokens.append(raw_token),
    )

    client.cookies.set(
        settings.session_cookie_name,
        "test-session-token",
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/logout",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "You have been logged out."

    assert revoked_tokens == ["test-session-token"]

    cookie_headers = response.headers.get_list("set-cookie")

    assert any(
        header.startswith(settings.session_cookie_name + "=")
        and "max-age=0" in header.lower()
        for header in cookie_headers
    )

    assert any(
        header.startswith(settings.csrf_cookie_name + "=")
        and "max-age=0" in header.lower()
        for header in cookie_headers
    )


def test_me_rejects_unauthenticated_request(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401

    error = response.json()["error"]

    assert error["code"] == "UNAUTHORIZED"
    assert error["message"] == "Authentication required"
    assert error["request_id"]


def test_invalid_email_verification_token_returns_safe_error(
    client,
    monkeypatch,
):
    def reject_token(db, raw_token):
        raise auth_api.InvalidVerificationTokenError(
            "The verification link is invalid or has expired"
        )

    monkeypatch.setattr(
        auth_api,
        "verify_email",
        reject_token,
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/verify-email",
        headers=headers,
        json={
            "token": "invalid-verification-token",
        },
    )

    assert response.status_code == 400

    error = response.json()["error"]

    assert error["code"] == "BAD_REQUEST"
    assert error["message"] == (
        "The verification link is invalid or has expired"
    )

    assert "invalid-verification-token" not in response.text


def test_invalid_password_reset_token_returns_safe_error(
    client,
    monkeypatch,
):
    def reject_token(db, raw_token, new_password):
        raise auth_api.InvalidPasswordResetTokenError(
            "The password-reset link is invalid or has expired"
        )

    monkeypatch.setattr(
        auth_api,
        "reset_password",
        reject_token,
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/password-reset/confirm",
        headers=headers,
        json={
            "token": "invalid-reset-token",
            "new_password": "NewStrongPassword123!",
        },
    )

    assert response.status_code == 400

    error = response.json()["error"]

    assert error["code"] == "BAD_REQUEST"
    assert error["message"] == (
        "The password-reset link is invalid or has expired"
    )

    assert "invalid-reset-token" not in response.text
    assert "NewStrongPassword123!" not in response.text


def test_successful_password_reset_clears_auth_cookies(
    client,
    monkeypatch,
):
    reset_calls = []

    monkeypatch.setattr(
        auth_api,
        "reset_password",
        lambda db, raw_token, new_password: reset_calls.append(
            (raw_token, new_password)
        ),
    )

    client.cookies.set(
        settings.session_cookie_name,
        "old-session-token",
        domain="testserver.local",
        path="/",
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/password-reset/confirm",
        headers=headers,
        json={
            "token": "valid-reset-token",
            "new_password": "NewStrongPassword123!",
        },
    )

    assert response.status_code == 200

    assert reset_calls == [
        ("valid-reset-token", "NewStrongPassword123!")
    ]

    assert response.json()["message"] == (
        "Your password has been reset. Please log in again."
    )

    cookie_headers = response.headers.get_list("set-cookie")

    assert any(
        header.startswith(settings.session_cookie_name + "=")
        and "max-age=0" in header.lower()
        for header in cookie_headers
    )

    assert any(
        header.startswith(settings.csrf_cookie_name + "=")
        and "max-age=0" in header.lower()
        for header in cookie_headers
    )

    assert "valid-reset-token" not in response.text
    assert "NewStrongPassword123!" not in response.text


def test_csrf_endpoint_prevents_response_caching(client):
    response = client.get("/api/auth/csrf")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_csrf_rejects_untrusted_origin(client, monkeypatch):
    login_called = False

    def mock_login_user(*args, **kwargs):
        nonlocal login_called
        login_called = True

    monkeypatch.setattr(auth_api, "login_user", mock_login_user)

    headers = get_csrf_headers(client)
    headers["Origin"] = "https://attacker.example"

    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "email": "person@example.com",
            "password": "CorrectPassword123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert login_called is False


def test_csrf_rejects_missing_origin(client, monkeypatch):
    login_called = False

    def mock_login_user(*args, **kwargs):
        nonlocal login_called
        login_called = True

    monkeypatch.setattr(auth_api, "login_user", mock_login_user)

    headers = get_csrf_headers(client)
    headers.pop("Origin")

    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "email": "person@example.com",
            "password": "CorrectPassword123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert login_called is False


def test_csrf_rejects_mismatched_token(client, monkeypatch):
    login_called = False

    def mock_login_user(*args, **kwargs):
        nonlocal login_called
        login_called = True

    monkeypatch.setattr(auth_api, "login_user", mock_login_user)

    headers = get_csrf_headers(client)
    headers["X-CSRF-Token"] = "different-csrf-token"

    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "email": "person@example.com",
            "password": "CorrectPassword123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert login_called is False


def test_cors_preflight_allows_configured_frontend(client):
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": settings.frontend_url,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,x-csrf-token"
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        settings.frontend_url
    )
    assert response.headers["access-control-allow-credentials"] == "true"

    allowed_headers = response.headers[
        "access-control-allow-headers"
    ].lower()

    assert "x-csrf-token" in allowed_headers
    assert "content-type" in allowed_headers


def test_cors_preflight_rejects_untrusted_origin(client):
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,x-csrf-token"
            ),
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_csrf_cookie_has_expected_lifetime_and_security_attributes(client):
    response = client.get("/api/auth/csrf")

    assert response.status_code == 200

    cookie_headers = response.headers.get_list("set-cookie")
    csrf_cookie_header = next(
        header
        for header in cookie_headers
        if header.startswith(settings.csrf_cookie_name + "=")
    )

    cookie = csrf_cookie_header.lower()

    assert "max-age=86400" in cookie
    assert "path=/" in cookie
    assert "samesite=lax" in cookie
    assert "httponly" not in cookie
    assert "secure" not in cookie


def test_session_cookie_has_expected_lifetime_and_security_attributes(
    client,
    monkeypatch,
):
    user = create_verified_user()

    monkeypatch.setattr(
        auth_api,
        "login_user",
        lambda db, email, password: SimpleNamespace(
            user=user,
            session_token="test-session-cookie-token",
        ),
    )

    headers = get_csrf_headers(client)

    response = client.post(
        "/api/auth/login",
        headers=headers,
        json={
            "email": "person@example.com",
            "password": "CorrectPassword123!",
        },
    )

    assert response.status_code == 200

    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie_header = next(
        header
        for header in cookie_headers
        if header.startswith(settings.session_cookie_name + "=")
    )

    cookie = session_cookie_header.lower()

    assert "max-age=86400" in cookie
    assert "path=/" in cookie
    assert "samesite=lax" in cookie
    assert "httponly" in cookie
    assert "secure" not in cookie
