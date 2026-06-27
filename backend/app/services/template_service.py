from __future__ import annotations

import uuid

from app.schemas.template import (
    BankTemplateCreate,
    BankTemplateResponse,
    BankTemplateVersionResponse,
    CompanyJournalTemplateCreate,
    CompanyJournalTemplateResponse,
    CompanyJournalTemplateVersionResponse,
)

_bank_templates: dict[str, BankTemplateResponse] = {}
_journal_templates: dict[str, CompanyJournalTemplateResponse] = {}


def create_bank_template(payload: BankTemplateCreate) -> BankTemplateResponse:
    template_id = str(uuid.uuid4())
    response = BankTemplateResponse(
        id=template_id,
        company_id=payload.company_id,
        name=payload.name,
        bank_name=payload.bank_name,
        bank_account_id=payload.bank_account_id,
        status="active",
        latest_version=BankTemplateVersionResponse(version_no=1, **payload.version.model_dump()),
    )
    _bank_templates[template_id] = response
    return response


def list_bank_templates(company_id: str | None = None) -> list[BankTemplateResponse]:
    templates = list(_bank_templates.values())
    if company_id is not None:
        templates = [t for t in templates if t.company_id == company_id]
    return templates


def create_journal_template(
    payload: CompanyJournalTemplateCreate,
) -> CompanyJournalTemplateResponse:
    template_id = str(uuid.uuid4())
    response = CompanyJournalTemplateResponse(
        id=template_id,
        company_id=payload.company_id,
        name=payload.name,
        status="active",
        latest_version=CompanyJournalTemplateVersionResponse(
            version_no=1, **payload.version.model_dump()
        ),
    )
    _journal_templates[template_id] = response
    return response


def list_journal_templates(
    company_id: str | None = None,
) -> list[CompanyJournalTemplateResponse]:
    templates = list(_journal_templates.values())
    if company_id is not None:
        templates = [t for t in templates if t.company_id == company_id]
    return templates
