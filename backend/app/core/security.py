"""Password hashing (argon2id) and token primitives.

Design:
* Access tokens are short-lived **JWTs** (stateless, verified by signature).
* Refresh tokens are long, opaque random strings. We store only their SHA-256
  **hash** in the DB, so a database leak can't be used to mint sessions, and we
  can revoke/rotate them. (Refresh-token rotation is implemented in the auth
  router.)
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ..config import settings

_ph = PasswordHasher()


# --- Passwords ---
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# --- Access tokens (JWT) ---
def create_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode + validate an access token. Raises ``jwt.PyJWTError`` on failure."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# --- Refresh tokens (opaque, hashed at rest) ---
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
