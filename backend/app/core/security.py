from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

_ALGO = "HS256"


class TokenError(Exception):
    """JWT 过期、签名错误或格式非法。"""


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *, user_id: str, roles: list[str], ttl_minutes: int, secret: str
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGO)


def decode_access_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[_ALGO])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
