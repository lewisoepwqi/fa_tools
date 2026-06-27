from typing import Any

from fastapi import APIRouter

from app.api.deps import DbSession
from app.models.audit import AuditLog

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=list[Any])
def list_audit_logs(db: DbSession) -> list[Any]:
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "company_id": r.company_id,
            "actor_id": r.actor_id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "before_json": r.before_json,
            "after_json": r.after_json,
            "ip_address": r.ip_address,
            "user_agent": r.user_agent,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
