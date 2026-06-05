"""Symmetric encryption for Bring-Your-Own-Key provider secrets.

User-supplied LLM API keys are encrypted with Fernet (AES-128-CBC + HMAC)
before they ever touch the database. The key lives only in ``FERNET_KEY`` env.
We also keep a non-sensitive ``last4`` for display in the UI.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import settings


@lru_cache
def _box() -> Fernet:
    # Lazily constructed so importing this module doesn't require a valid key
    # (e.g. during unit tests of unrelated logic).
    return Fernet(settings.fernet_key)


def encrypt_secret(plaintext: str) -> str:
    return _box().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _box().decrypt(token.encode()).decode()


def last4(value: str) -> str:
    return value[-4:] if len(value) >= 4 else "****"
