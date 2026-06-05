import uuid

import jwt
import pytest

from app.core.crypto import decrypt_secret, encrypt_secret, last4
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("hunter2hunter2")
    assert h != "hunter2hunter2"
    assert verify_password("hunter2hunter2", h)
    assert not verify_password("wrong-password", h)


def test_verify_bad_hash_is_false_not_error():
    assert verify_password("anything", "not-a-real-argon2-hash") is False


def test_access_token_roundtrip():
    uid = str(uuid.uuid4())
    token = create_access_token(uid)
    payload = decode_access_token(token)
    assert payload["sub"] == uid
    assert payload["type"] == "access"


def test_decode_rejects_garbage():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not.a.real.token")


def test_refresh_token_hash_is_stable_and_opaque():
    raw = generate_refresh_token()
    assert hash_token(raw) == hash_token(raw)
    assert len(hash_token(raw)) == 64
    assert raw not in hash_token(raw)


def test_fernet_roundtrip_and_last4():
    secret = "sk-or-v1-supersecret"
    enc = encrypt_secret(secret)
    assert enc != secret
    assert decrypt_secret(enc) == secret
    assert last4(secret) == "cret"
    assert last4("ab") == "****"
