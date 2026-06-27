import uuid

from fastapi import APIRouter

from app.schemas.rule import RuleCreate, RuleResponse, RuleVersionResponse

router = APIRouter(prefix="/api/rules", tags=["rules"])

_rules: dict[str, RuleResponse] = {}


@router.post("", response_model=RuleResponse)
def create_rule(payload: RuleCreate) -> RuleResponse:
    rule_id = str(uuid.uuid4())
    response = RuleResponse(
        id=rule_id,
        company_id=payload.company_id,
        name=payload.name,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        status="active",
        latest_version=RuleVersionResponse(version_no=1, **payload.version.model_dump()),
    )
    _rules[rule_id] = response
    return response


@router.get("", response_model=list[RuleResponse])
def list_rules(company_id: str | None = None) -> list[RuleResponse]:
    rules = list(_rules.values())
    if company_id is not None:
        rules = [r for r in rules if r.company_id == company_id]
    return rules
