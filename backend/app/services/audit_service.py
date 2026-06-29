from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.crypto import mask_account
from app.models.audit import AuditLog

_SECRET_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "field_encryption_key",
    "secret_key",
}
_ACCOUNT_KEY_HINT = "account_no"


def redact(payload: dict | None) -> dict | None:
    """递归脱敏敏感字段。

    密钥/口令类字段（password/password_hash/token 等）→ "***"
    账号字段（名称包含 account_no）且为字符串 → mask_account(...)
    嵌套 dict/list 递归处理。
    None 透传。
    """
    if payload is None:
        return None

    def _walk(value):
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                lk = str(k).lower()
                if lk in _SECRET_KEYS:
                    out[k] = "***"
                elif _ACCOUNT_KEY_HINT in lk and isinstance(v, str):
                    out[k] = mask_account(v)
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(value, (list, tuple)):
            return [_walk(i) for i in value]
        return value

    return _walk(payload)


def _json_safe(value: Any) -> Any:
    """递归把 datetime/date/Decimal 等转为 JSON 可序列化的字符串/基本类型。

    SQLAlchemy 的 JSON 列无法直接序列化 datetime 等对象，审计快照里若
    包含这些类型（如带时间戳的响应）会触发 StatementError。
    """
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    # Decimal、date、enum 等其他类型一律退化为字符串。
    return str(value)


def build_audit_event(
    company_id: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    ip_address: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_json": _json_safe(redact(before)),
        "after_json": _json_safe(redact(after)),
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": datetime.now(UTC).isoformat(),
    }


def record_audit_event(
    db: Session,
    *,
    company_id: str | None,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    event = build_audit_event(
        company_id,
        actor_id,
        action,
        entity_type,
        entity_id,
        before,
        after,
        ip_address,
        user_agent,
    )
    db.add(
        AuditLog(
            id=str(uuid4()),
            company_id=event["company_id"],
            actor_id=event["actor_id"],
            action=event["action"],
            entity_type=event["entity_type"],
            entity_id=event["entity_id"],
            before_json=event["before_json"],
            after_json=event["after_json"],
            ip_address=event["ip_address"],
            user_agent=event["user_agent"],
        )
    )
    db.commit()


def audit_ctx(request) -> dict:
    """从请求对象提取 ip_address 和 user_agent，供路由传入审计记录。

    处理 request.client 为 None 的情况（如测试或某些代理配置）。
    """
    client = getattr(request, "client", None)
    return {
        "ip_address": getattr(client, "host", None) if client else None,
        "user_agent": request.headers.get("user-agent"),
    }
