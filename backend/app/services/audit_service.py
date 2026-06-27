from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


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
        "before_json": before,
        "after_json": after,
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
