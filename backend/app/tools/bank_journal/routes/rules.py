import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    accessible_company_filter,
    require,
    require_company_access,
)
from app.core.enums import RecordStatus
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event
from app.tools.bank_journal.models.conversion import ConversionRunRuleVersion
from app.tools.bank_journal.models.rule import Rule, RuleVersion
from app.tools.bank_journal.schemas.pagination import Page
from app.tools.bank_journal.schemas.rule import (
    RuleCreate,
    RuleResponse,
    RuleVersionCreate,
    RuleVersionResponse,
)

router = APIRouter(prefix="/api/tools/bank-journal/rules", tags=["rules"])


class RuleReorderItem(BaseModel):
    rule_id: str
    priority: int


class RuleReorderRequest(BaseModel):
    items: list[RuleReorderItem]


@router.post(
    "",
    response_model=RuleResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_rule(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    payload: RuleCreate,
) -> RuleResponse:
    require_company_access(user, payload.company_id)
    payload.version.created_by = user.id
    rule_id = str(uuid.uuid4())
    parent = Rule(
        id=rule_id,
        company_id=payload.company_id,
        name=payload.name,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        status="active",
    )
    version = RuleVersion(
        id=str(uuid.uuid4()),
        rule_id=rule_id,
        version_no=1,
        priority=payload.version.priority,
        conditions_json=payload.version.conditions_json,
        actions_json=payload.version.actions_json,
        allow_auto_confirm=payload.version.allow_auto_confirm,
        created_by=payload.version.created_by,
    )
    db.add(parent)
    db.flush()  # rules 先落库，version 的外键引用方有效
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    response = _to_response(parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action="rule.created",
        entity_type="rule",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.get(
    "",
    response_model=Page[RuleResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_rules(
    db: DbSession,
    user: CurrentUserDep,
    company_id: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[RuleResponse]:
    """列表（分页）。

    可选过滤：company_id / scope_type(+scope_id)。
    scope 过滤用于模板详情页展示"绑定了哪些规则"（规则用松散 scope_type+scope_id 约定绑定）。
    scope_id 通常需配合 scope_type 一起传（按约定 scope_type=bank_template, scope_id=<模板id>）。
    """
    query = db.query(Rule)
    if company_id is not None:
        query = query.filter(Rule.company_id == company_id)
    # 租户收窄：accessible 非 None 时仅返回可访问公司的行
    accessible = accessible_company_filter(user)
    if accessible is not None:
        query = query.filter(Rule.company_id.in_(accessible))
    if scope_type is not None:
        query = query.filter(Rule.scope_type == scope_type)
    if scope_id is not None:
        query = query.filter(Rule.scope_id == scope_id)
    # 软删除项不在列表/下拉中展示
    query = query.filter(Rule.status != RecordStatus.DELETED.value)
    total = query.count()
    parents = query.order_by(Rule.status).offset(offset).limit(limit).all()
    if not parents:
        return Page[RuleResponse](items=[], total=total, limit=limit, offset=offset)
    parent_ids = [p.id for p in parents]
    latest_no = (
        db.query(
            RuleVersion.rule_id.label("pid"),
            func.max(RuleVersion.version_no).label("mv"),
        )
        .filter(RuleVersion.rule_id.in_(parent_ids))
        .group_by(RuleVersion.rule_id)
        .subquery()
    )
    versions = (
        db.query(RuleVersion)
        .join(
            latest_no,
            (RuleVersion.rule_id == latest_no.c.pid)
            & (RuleVersion.version_no == latest_no.c.mv),
        )
        .all()
    )
    by_parent = {v.rule_id: v for v in versions}
    return Page[RuleResponse](
        items=[_to_response(p, by_parent.get(p.id)) for p in parents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require(Permission.READ))],
)
def get_rule(db: DbSession, user: CurrentUserDep, rule_id: str) -> RuleResponse:
    """规则详情（含最新版本）。不存在则 404，无权访问则 403。"""
    parent = _get_rule_or_404(db, rule_id)
    require_company_access(user, parent.company_id)  # 跨公司读取拦截
    latest = _latest_rule_version(db, rule_id)
    return _to_response(parent, latest)


@router.post(
    "/{rule_id}/versions",
    response_model=RuleResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_rule_version(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    rule_id: str,
    payload: RuleVersionCreate,
) -> RuleResponse:
    """编辑规则=创建新版本（旧版本不可变）。"""
    parent = _get_rule_or_404(db, rule_id)
    require_company_access(user, parent.company_id)
    payload.created_by = user.id
    before_latest = _latest_rule_version(db, rule_id)
    new_version_no = (before_latest.version_no + 1) if before_latest else 1
    version = RuleVersion(
        id=str(uuid.uuid4()),
        rule_id=rule_id,
        version_no=new_version_no,
        priority=payload.priority,
        conditions_json=payload.conditions_json,
        actions_json=payload.actions_json,
        allow_auto_confirm=payload.allow_auto_confirm,
        created_by=payload.created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    response = _to_response(parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action="rule.modified",
        entity_type="rule",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.get(
    "/{rule_id}/versions",
    response_model=list[RuleVersionResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_rule_versions(
    db: DbSession, user: CurrentUserDep, rule_id: str
) -> list[RuleVersionResponse]:
    """规则版本历史。不存在则 404，无权访问则 403。"""
    parent = _get_rule_or_404(db, rule_id)
    require_company_access(user, parent.company_id)  # 跨公司读取拦截
    versions = (
        db.query(RuleVersion)
        .filter(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version_no.desc())
        .all()
    )
    return [
        RuleVersionResponse(
            version_no=version.version_no,
            priority=version.priority,
            conditions_json=version.conditions_json,
            actions_json=version.actions_json,
            allow_auto_confirm=version.allow_auto_confirm,
            created_by=version.created_by,
        )
        for version in versions
    ]


@router.patch(
    "/{rule_id}/status",
    response_model=RuleResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def update_rule_status(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    rule_id: str,
    status: str,
) -> RuleResponse:
    """停用/启用规则。"""
    if status not in {RecordStatus.ACTIVE.value, RecordStatus.INACTIVE.value}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {status}",
        )
    parent = _get_rule_or_404(db, rule_id)
    require_company_access(user, parent.company_id)
    parent.status = status
    db.commit()
    db.refresh(parent)
    latest = _latest_rule_version(db, rule_id)
    response = _to_response(parent, latest)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action=(
            "rule.disabled"
            if status == RecordStatus.INACTIVE.value
            else "rule.enabled"
        ),
        entity_type="rule",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.delete(
    "/{rule_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def delete_rule(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    rule_id: str,
) -> None:
    """软删除规则（status→deleted）。

    引用拦截最严格：ConversionRunRuleVersion.rule_version_id 是 NOT NULL，
    一旦任一规则版本被批次引用即 409（保证历史批次可追溯）。
    """
    parent = _get_rule_or_404(db, rule_id)
    require_company_access(user, parent.company_id)

    version_ids = [
        v.id
        for v in db.query(RuleVersion.id).filter(RuleVersion.rule_id == rule_id).all()
    ]
    run_count = (
        db.query(ConversionRunRuleVersion)
        .filter(ConversionRunRuleVersion.rule_version_id.in_(version_ids))
        .count()
        if version_ids
        else 0
    )
    if run_count > 0:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"该规则已被 {run_count} 个转换批次引用，无法删除（需保留历史可追溯）。",
        )

    before = _to_response(parent, _latest_rule_version(db, rule_id))
    parent.status = RecordStatus.DELETED.value
    db.commit()
    db.refresh(parent)
    record_audit_event(
        db,
        company_id=parent.company_id,
        actor_id=user.id,
        action="rule.deleted",
        entity_type="rule",
        entity_id=rule_id,
        before=before.model_dump(),
        **audit_ctx(request),
    )


@router.post(
    "/reorder",
    response_model=dict[str, Any],
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def reorder_rules(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    payload: RuleReorderRequest,
) -> dict[str, Any]:
    """批量调整规则优先级（PRD §6.6 / 技术设计 §11.5）。

    为每条规则创建一个新版本承载新 priority（保持版本化不可变语义）。
    """
    updated: list[dict[str, Any]] = []
    for item in payload.items:
        parent = _get_rule_or_404(db, item.rule_id)  # 校验规则存在
        # 派生公司写校验：reorder 按 rule_id 携带，逐条校验其公司可访问
        require_company_access(user, parent.company_id)
        before_latest = _latest_rule_version(db, item.rule_id)
        if before_latest is None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Rule has no version: {item.rule_id}",
            )
        if before_latest.priority == item.priority:
            updated.append({"rule_id": item.rule_id, "priority": item.priority})
            continue
        new_version = RuleVersion(
            id=str(uuid.uuid4()),
            rule_id=item.rule_id,
            version_no=before_latest.version_no + 1,
            priority=item.priority,
            conditions_json=before_latest.conditions_json,
            actions_json=before_latest.actions_json,
            allow_auto_confirm=before_latest.allow_auto_confirm,
            created_by=before_latest.created_by,
        )
        db.add(new_version)
        updated.append({"rule_id": item.rule_id, "priority": item.priority})
    db.commit()
    record_audit_event(
        db,
        company_id=None,
        actor_id=user.id,
        action="rule.priority_changed",
        entity_type="rule",
        entity_id=",".join(item.rule_id for item in payload.items),
        after={"updated": updated},
        **audit_ctx(request),
    )
    return {"updated": updated}


def _get_rule_or_404(db: DbSession, rule_id: str) -> Rule:
    parent = db.query(Rule).filter(Rule.id == rule_id).first()
    if parent is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Rule not found: {rule_id}",
        )
    return parent


def _latest_rule_version(db: DbSession, rule_id: str) -> RuleVersion | None:
    return (
        db.query(RuleVersion)
        .filter(RuleVersion.rule_id == rule_id)
        .order_by(RuleVersion.version_no.desc())
        .first()
    )


def _to_response(parent: Rule, version: RuleVersion | None) -> RuleResponse:
    return RuleResponse(
        id=parent.id,
        company_id=parent.company_id,
        name=parent.name,
        scope_type=parent.scope_type,
        scope_id=parent.scope_id,
        status=parent.status,
        latest_version=RuleVersionResponse(
            version_no=version.version_no,
            priority=version.priority,
            conditions_json=version.conditions_json,
            actions_json=version.actions_json,
            allow_auto_confirm=version.allow_auto_confirm,
            created_by=version.created_by,
        ),
    )
