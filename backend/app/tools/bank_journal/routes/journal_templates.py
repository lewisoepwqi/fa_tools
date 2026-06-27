from fastapi import APIRouter

from app.api.deps import DbSession
from app.services.audit_service import record_audit_event
from app.tools.bank_journal.schemas.template import (
    CompanyJournalTemplateCreate,
    CompanyJournalTemplateResponse,
    CompanyJournalTemplateVersionCreate,
    CompanyJournalTemplateVersionResponse,
)
from app.tools.bank_journal.services import template_service

router = APIRouter(
    prefix="/api/tools/bank-journal/journal-templates", tags=["journal-templates"]
)


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


@router.get("/{template_id}", response_model=CompanyJournalTemplateResponse)
def get_journal_template(
    db: DbSession, template_id: str
) -> CompanyJournalTemplateResponse:
    """日记账模板详情（含最新版本）。不存在则 404。"""
    return template_service.get_journal_template(db, template_id)


@router.post("/{template_id}/versions", response_model=CompanyJournalTemplateResponse)
def create_journal_template_version(
    db: DbSession, template_id: str, payload: CompanyJournalTemplateVersionCreate
) -> CompanyJournalTemplateResponse:
    """编辑日记账模板=创建新版本。"""
    before = template_service.get_journal_template(db, template_id)
    response = template_service.create_journal_template_version(db, template_id, payload)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="journal_template.modified",
        entity_type="company_journal_template",
        entity_id=response.id,
        before=before.model_dump(),
        after=response.model_dump(),
    )
    return response


@router.get(
    "/{template_id}/versions",
    response_model=list[CompanyJournalTemplateVersionResponse],
)
def list_journal_template_versions(
    db: DbSession, template_id: str
) -> list[CompanyJournalTemplateVersionResponse]:
    """日记账模板版本历史。"""
    return template_service.list_journal_template_versions(db, template_id)


@router.patch("/{template_id}/status", response_model=CompanyJournalTemplateResponse)
def update_journal_template_status(
    db: DbSession, template_id: str, status: str
) -> CompanyJournalTemplateResponse:
    """停用/启用日记账模板。校验委托服务层。"""
    before = template_service.get_journal_template(db, template_id)
    response = template_service.set_journal_template_status(db, template_id, status)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=None,
        action=(
            "journal_template.disabled"
            if response.status == "inactive"
            else "journal_template.enabled"
        ),
        entity_type="company_journal_template",
        entity_id=response.id,
        before=before.model_dump(),
        after=response.model_dump(),
    )
    return response
