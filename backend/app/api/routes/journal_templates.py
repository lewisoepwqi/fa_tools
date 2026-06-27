from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.template import (
    CompanyJournalTemplateCreate,
    CompanyJournalTemplateResponse,
)
from app.services import template_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/journal-templates", tags=["journal-templates"])


@router.post("", response_model=CompanyJournalTemplateResponse)
def create_journal_template(
    db: DbSession, payload: CompanyJournalTemplateCreate
) -> CompanyJournalTemplateResponse:
    response = template_service.create_journal_template(db, payload)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="journal_template.created",
        entity_type="company_journal_template",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get("", response_model=list[CompanyJournalTemplateResponse])
def list_journal_templates(
    db: DbSession, company_id: str | None = None
) -> list[CompanyJournalTemplateResponse]:
    return template_service.list_journal_templates(db, company_id)
