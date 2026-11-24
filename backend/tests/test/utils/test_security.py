import re

import pytest

from app.utils.security import (
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)


# ------------------------------------------------------------
# Password hashing tests
# ------------------------------------------------------------

def test_hash_password_uses_argon2id():
    password_hash = hash_password("Strong-Test-Password-123!")

    assert password_hash.startswith("$argon2id$")


def test_hash_password_generates_unique_salts():
    password = "Strong-Test-Password-123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash


def test_verify_password_accepts_correct_password():
    password = "Strong-Test-Password-123!"
    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_verify_password_rejects_incorrect_password():
    password_hash = hash_password("Strong-Test-Password-123!")

    assert verify_password("Incorrect-Password", password_hash) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("Some-Password", "not-a-valid-hash") is False


def test_verify_password_rejects_non_string_values():
    assert verify_password(None, "some-hash") is False
    assert verify_password("Some-Password", None) is False


def test_hash_password_rejects_empty_password():
    with pytest.raises(ValueError):
        hash_password("")


def test_hash_password_rejects_non_string_password():
    with pytest.raises(ValueError):
        hash_password(None)


# ------------------------------------------------------------
# Secure token generation tests
# ------------------------------------------------------------

def test_generate_secure_token_returns_url_safe_string():
    token = generate_secure_token()

    assert isinstance(token, str)
    assert len(token) > 0
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token)


def test_generate_secure_token_generates_unique_values():
    first_token = generate_secure_token()
    second_token = generate_secure_token()

    assert first_token != second_token


def test_generate_secure_token_uses_requested_entropy_size():
    token = generate_secure_token(token_bytes=32)

    # 32 random bytes encoded as URL-safe Base64 without padding.
    assert len(token) == 43


def test_generate_secure_token_rejects_invalid_size():
    with pytest.raises(ValueError):
        generate_secure_token(token_bytes=0)

    with pytest.raises(ValueError):
        generate_secure_token(token_bytes=-1)

    with pytest.raises(ValueError):
        generate_secure_token(token_bytes="32")


# ------------------------------------------------------------
# Token hashing tests
# ------------------------------------------------------------

def test_hash_token_returns_sha256_hex_digest():
    token_hash = hash_token("example-secure-token")

    assert len(token_hash) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", token_hash)


def test_hash_token_is_deterministic():
    token = "example-secure-token"

    assert hash_token(token) == hash_token(token)


def test_hash_token_changes_for_different_tokens():
    assert hash_token("first-token") != hash_token("second-token")


def test_hash_token_does_not_return_original_token():
    token = "example-secure-token"

    assert hash_token(token) != token


def test_hash_token_rejects_empty_token():
    with pytest.raises(ValueError):
        hash_token("")


def test_hash_token_rejects_non_string_token():
    with pytest.raises(ValueError):
        hash_token(None)
