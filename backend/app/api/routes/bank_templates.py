from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.template import BankTemplateCreate, BankTemplateResponse
from app.services import template_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/bank-templates", tags=["bank-templates"])


@router.post("", response_model=BankTemplateResponse)
def create_bank_template(
    db: DbSession, payload: BankTemplateCreate
) -> BankTemplateResponse:
    response = template_service.create_bank_template(db, payload)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="bank_template.created",
        entity_type="bank_template",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get("", response_model=list[BankTemplateResponse])
def list_bank_templates(
    db: DbSession, company_id: str | None = None
) -> list[BankTemplateResponse]:
    return template_service.list_bank_templates(db, company_id)
