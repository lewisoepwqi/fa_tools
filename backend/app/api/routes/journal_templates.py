from fastapi import APIRouter

from app.schemas.template import (
    CompanyJournalTemplateCreate,
    CompanyJournalTemplateResponse,
)
from app.services import template_service

router = APIRouter(prefix="/api/journal-templates", tags=["journal-templates"])


@router.post("", response_model=CompanyJournalTemplateResponse)
def create_journal_template(
    payload: CompanyJournalTemplateCreate,
) -> CompanyJournalTemplateResponse:
    return template_service.create_journal_template(payload)


@router.get("", response_model=list[CompanyJournalTemplateResponse])
def list_journal_templates(
    company_id: str | None = None,
) -> list[CompanyJournalTemplateResponse]:
    return template_service.list_journal_templates(company_id)
