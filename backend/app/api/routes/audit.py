from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUserDep, DbSession, accessible_company_filter, require
from app.core.permissions import Permission
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.tools.bank_journal.schemas.pagination import Page

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=Page[AuditLogResponse],
    dependencies=[Depends(require(Permission.AUDIT_VIEW))],
)
def list_audit_logs(
    db: DbSession,
    user: CurrentUserDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[AuditLogResponse]:
    base = db.query(AuditLog)
    # 租户收窄：scoped 用户（accessible 非 None）仅见本公司审计行。
    # company_id 为 NULL 的行属平台级（如登录等），仅跨公司角色（accessible 为 None）可见。
    accessible = accessible_company_filter(user)
    if accessible is not None:
        base = base.filter(AuditLog.company_id.in_(accessible))
    base = base.order_by(AuditLog.created_at.desc())
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
