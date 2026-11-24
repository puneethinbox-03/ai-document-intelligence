import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


# ------------------------------------------------------------
# Password hashing configuration
# ------------------------------------------------------------

# Explicit Argon2id parameters.
# These can be adjusted later based on production performance tests.

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


# ------------------------------------------------------------
# Password utilities
# ------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hash a plaintext password using Argon2id.

    A unique random salt is generated automatically
    for every password hash.
    """

    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    return _password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    Verify a plaintext password against an Argon2id hash.

    Returns False for incorrect passwords or invalid hashes.
    """

    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False

    try:
        return _password_hasher.verify(password_hash, password)

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


# ------------------------------------------------------------
# Secure token generation
# ------------------------------------------------------------

def generate_secure_token(token_bytes: int = 32) -> str:
    """
    Generate a cryptographically secure URL-safe token.

    Default entropy: 32 random bytes (256 bits).
    """

    if not isinstance(token_bytes, int) or isinstance(token_bytes, bool):
        raise ValueError("Token size must be a positive integer")

    if token_bytes <= 0:
        raise ValueError("Token size must be a positive integer")

    return secrets.token_urlsafe(token_bytes)


# ------------------------------------------------------------
# Token hashing
# ------------------------------------------------------------

def hash_token(token: str) -> str:
    """
    Return the SHA-256 hexadecimal digest of a token.

    Store this digest instead of the original token.
    """

    if not isinstance(token, str) or not token:
        raise ValueError("Token must be a non-empty string")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()
