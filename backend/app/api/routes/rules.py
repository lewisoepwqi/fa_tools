import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.models.rule import Rule, RuleVersion
from app.schemas.rule import RuleCreate, RuleResponse, RuleVersionResponse
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/rules", tags=["rules"])


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
        latest = (
            db.query(RuleVersion)
            .filter(RuleVersion.rule_id == parent.id)
            .order_by(RuleVersion.version_no.desc())
            .first()
        )
        out.append(_to_response(parent, latest))
    return out


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
