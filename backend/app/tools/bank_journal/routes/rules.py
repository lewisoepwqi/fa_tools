import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.api.deps import DbSession
from app.core.enums import RecordStatus
from app.services.audit_service import record_audit_event
from app.tools.bank_journal.models.rule import Rule, RuleVersion
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


@router.post("", response_model=RuleResponse)
def create_rule(db: DbSession, payload: RuleCreate) -> RuleResponse:
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
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    response = _to_response(parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="rule.created",
        entity_type="rule",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get("", response_model=list[RuleResponse])
def list_rules(db: DbSession, company_id: str | None = None) -> list[RuleResponse]:
    query = db.query(Rule)
    if company_id is not None:
        query = query.filter(Rule.company_id == company_id)
    out: list[RuleResponse] = []
    for parent in query.all():
        latest = _latest_rule_version(db, parent.id)
        out.append(_to_response(parent, latest))
    return out


@router.get("/{rule_id}", response_model=RuleResponse)
def get_rule(db: DbSession, rule_id: str) -> RuleResponse:
    """规则详情（含最新版本）。不存在则 404。"""
    parent = _get_rule_or_404(db, rule_id)
    latest = _latest_rule_version(db, rule_id)
    return _to_response(parent, latest)


@router.post("/{rule_id}/versions", response_model=RuleResponse)
def create_rule_version(
    db: DbSession, rule_id: str, payload: RuleVersionCreate
) -> RuleResponse:
    """编辑规则=创建新版本（旧版本不可变）。"""
    parent = _get_rule_or_404(db, rule_id)
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
        actor_id=response.latest_version.created_by,
        action="rule.modified",
        entity_type="rule",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get("/{rule_id}/versions", response_model=list[RuleVersionResponse])
def list_rule_versions(db: DbSession, rule_id: str) -> list[RuleVersionResponse]:
    """规则版本历史。"""
    _get_rule_or_404(db, rule_id)
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


@router.patch("/{rule_id}/status", response_model=RuleResponse)
def update_rule_status(db: DbSession, rule_id: str, status: str) -> RuleResponse:
    """停用/启用规则。"""
    if status not in {RecordStatus.ACTIVE.value, RecordStatus.INACTIVE.value}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {status}",
        )
    parent = _get_rule_or_404(db, rule_id)
    parent.status = status
    db.commit()
    db.refresh(parent)
    latest = _latest_rule_version(db, rule_id)
    response = _to_response(parent, latest)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=None,
        action=(
            "rule.disabled"
            if status == RecordStatus.INACTIVE.value
            else "rule.enabled"
        ),
        entity_type="rule",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.post("/reorder", response_model=dict[str, Any])
def reorder_rules(db: DbSession, payload: RuleReorderRequest) -> dict[str, Any]:
    """批量调整规则优先级（PRD §6.6 / 技术设计 §11.5）。

    为每条规则创建一个新版本承载新 priority（保持版本化不可变语义）。
    """
    updated: list[dict[str, Any]] = []
    for item in payload.items:
        _get_rule_or_404(db, item.rule_id)  # 校验规则存在
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
        actor_id=None,
        action="rule.priority_changed",
        entity_type="rule",
        entity_id=",".join(item.rule_id for item in payload.items),
        after={"updated": updated},
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
