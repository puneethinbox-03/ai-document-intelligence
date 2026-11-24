from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import dependencies
from app.models import User
from app.services.auth.session_service import InvalidSessionError


def make_request(headers=None):
    raw_headers = [
        (key.lower().encode(), value.encode())
        for key, value in (headers or {}).items()
    ]

    scope = {
        "type": "http",
        "asgi": {
            "version": "3.0",
        },
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/auth/test",
        "raw_path": b"/api/auth/test",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    return Request(scope)


def test_get_current_user_rejects_missing_session_cookie():
    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(
            session_token=None,
            db=Mock(),
        )

    assert exc.value.status_code == 401


def test_get_current_user_returns_authenticated_user(monkeypatch):
    user = Mock(spec=User)

    monkeypatch.setattr(
        dependencies,
        "get_authenticated_user",
        lambda db, raw_token: user,
    )

    result = dependencies.get_current_user(
        session_token="valid-session-token",
        db=Mock(),
    )

    assert result is user


def test_get_current_user_rejects_invalid_session(monkeypatch):
    def reject_session(db, raw_token):
        raise InvalidSessionError("Invalid session")

    monkeypatch.setattr(
        dependencies,
        "get_authenticated_user",
        reject_session,
    )

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(
            session_token="invalid-session-token",
            db=Mock(),
        )

    assert exc.value.status_code == 401


def test_csrf_rejects_missing_origin():
    request = make_request()

    with pytest.raises(HTTPException) as exc:
        dependencies.require_csrf(
            request=request,
            csrf_token_header="valid-token",
            csrf_cookie="valid-token",
        )

    assert exc.value.status_code == 403


def test_csrf_rejects_untrusted_origin():
    request = make_request({
        "origin": "https://attacker.example",
    })

    with pytest.raises(HTTPException) as exc:
        dependencies.require_csrf(
            request=request,
            csrf_token_header="valid-token",
            csrf_cookie="valid-token",
        )

    assert exc.value.status_code == 403


def test_csrf_rejects_origin_with_path():
    request = make_request({
        "origin": "http://localhost:3000/untrusted-path",
    })

    with pytest.raises(HTTPException) as exc:
        dependencies.require_csrf(
            request=request,
            csrf_token_header="valid-token",
            csrf_cookie="valid-token",
        )

    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    ("header_token", "cookie_token"),
    [
        (None, "valid-token"),
        ("valid-token", None),
        (None, None),
    ],
)
def test_csrf_rejects_missing_tokens(header_token, cookie_token):
    request = make_request({
        "origin": "http://localhost:3000",
    })

    with pytest.raises(HTTPException) as exc:
        dependencies.require_csrf(
            request=request,
            csrf_token_header=header_token,
            csrf_cookie=cookie_token,
        )

    assert exc.value.status_code == 403


def test_csrf_rejects_mismatched_tokens():
    request = make_request({
        "origin": "http://localhost:3000",
    })

    with pytest.raises(HTTPException) as exc:
        dependencies.require_csrf(
            request=request,
            csrf_token_header="header-token",
            csrf_cookie="different-cookie-token",
        )

    assert exc.value.status_code == 403


def test_csrf_accepts_matching_tokens_from_trusted_origin():
    request = make_request({
        "origin": "http://localhost:3000",
    })

    result = dependencies.require_csrf(
        request=request,
        csrf_token_header="matching-token",
        csrf_cookie="matching-token",
    )

    assert result is None


def test_csrf_accepts_configured_frontend_origin(monkeypatch):
    monkeypatch.setattr(
        dependencies.settings,
        "frontend_url",
        "https://frontend.example",
    )

    request = make_request({
        "origin": "https://frontend.example",
    })

    result = dependencies.require_csrf(
        request=request,
        csrf_token_header="matching-token",
        csrf_cookie="matching-token",
    )

    assert result is None


def test_csrf_can_be_disabled_by_configuration(monkeypatch):
    monkeypatch.setattr(
        dependencies.settings,
        "csrf_protection_enabled",
        False,
    )

    request = make_request()

    result = dependencies.require_csrf(
        request=request,
        csrf_token_header=None,
        csrf_cookie=None,
    )

    assert result is None
