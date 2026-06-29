from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.tools.bank_journal.schemas.pagination import Page

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogResponse])
def list_audit_logs(
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[AuditLogResponse]:
    base = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    total = base.count()
    rows = base.offset(offset).limit(limit).all()
    items = [
        AuditLogResponse(
            id=r.id,
            company_id=r.company_id,
            actor_id=r.actor_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            before_json=r.before_json,
            after_json=r.after_json,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    return Page[AuditLogResponse](items=items, total=total, limit=limit, offset=offset)
