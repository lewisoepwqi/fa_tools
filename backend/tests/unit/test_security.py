import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret"


def test_password_hash_roundtrip():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip_carries_claims():
    token = create_access_token(
        user_id="u1", roles=["admin"], ttl_minutes=60, secret=SECRET
    )
    claims = decode_access_token(token, SECRET)
    assert claims["sub"] == "u1"
    assert claims["roles"] == ["admin"]


def test_expired_token_raises():
    token = create_access_token(
        user_id="u1", roles=[], ttl_minutes=-1, secret=SECRET
    )
    with pytest.raises(TokenError):
        decode_access_token(token, SECRET)


def test_tampered_token_raises():
    token = create_access_token(
        user_id="u1", roles=[], ttl_minutes=60, secret=SECRET
    )
    with pytest.raises(TokenError):
        decode_access_token(token + "x", SECRET)


def test_wrong_secret_raises():
    token = create_access_token(
        user_id="u1", roles=[], ttl_minutes=60, secret=SECRET
    )
    with pytest.raises(TokenError):
        decode_access_token(token, "other-secret")
