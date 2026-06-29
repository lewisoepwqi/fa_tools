from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().field_encryption_key.encode("utf-8"))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def mask_account(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


class EncryptedString(TypeDecorator):
    """入库自动 Fernet 加密、读取自动解密的透明字符串列。None 透传。"""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt(value)
