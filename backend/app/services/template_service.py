from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.template import (
    BankTemplate,
    BankTemplateVersion,
    CompanyJournalTemplate,
    CompanyJournalTemplateVersion,
)
from app.schemas.template import (
    BankTemplateCreate,
    BankTemplateResponse,
    BankTemplateVersionResponse,
    CompanyJournalTemplateCreate,
    CompanyJournalTemplateResponse,
    CompanyJournalTemplateVersionResponse,
)


def create_bank_template(db: Session, payload: BankTemplateCreate) -> BankTemplateResponse:
    template_id = str(uuid.uuid4())
    parent = BankTemplate(
        id=template_id,
        company_id=payload.company_id,
        name=payload.name,
        bank_name=payload.bank_name,
        bank_account_id=payload.bank_account_id,
        status="active",
    )
    version = BankTemplateVersion(
        id=str(uuid.uuid4()),
        bank_template_id=template_id,
        version_no=1,
        file_type=payload.version.file_type,
        sheet_selector_json=payload.version.sheet_selector_json,
        header_row_index=payload.version.header_row_index,
        data_start_row_index=payload.version.data_start_row_index,
        field_aliases_json=payload.version.field_aliases_json,
        date_formats_json=payload.version.date_formats_json,
        amount_mode=payload.version.amount_mode,
        amount_config_json=payload.version.amount_config_json,
        unique_key_config_json=payload.version.unique_key_config_json,
        sample_file_id=payload.version.sample_file_id,
        created_by=payload.version.created_by,
    )
    db.add(parent)
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    return _bank_template_to_response(parent, version)


def list_bank_templates(db: Session, company_id: str | None = None) -> list[BankTemplateResponse]:
    query = db.query(BankTemplate)
    if company_id is not None:
        query = query.filter(BankTemplate.company_id == company_id)
    out: list[BankTemplateResponse] = []
    for parent in query.all():
        latest = (
            db.query(BankTemplateVersion)
            .filter(BankTemplateVersion.bank_template_id == parent.id)
            .order_by(BankTemplateVersion.version_no.desc())
            .first()
        )
        out.append(_bank_template_to_response(parent, latest))
    return out


def create_journal_template(
    db: Session, payload: CompanyJournalTemplateCreate
) -> CompanyJournalTemplateResponse:
    template_id = str(uuid.uuid4())
    parent = CompanyJournalTemplate(
        id=template_id,
        company_id=payload.company_id,
        name=payload.name,
        status="active",
    )
    version = CompanyJournalTemplateVersion(
        id=str(uuid.uuid4()),
        company_journal_template_id=template_id,
        version_no=1,
        file_type=payload.version.file_type,
        sheet_name=payload.version.sheet_name,
        header_row_index=payload.version.header_row_index,
        data_start_row_index=payload.version.data_start_row_index,
        columns_json=payload.version.columns_json,
        required_columns_json=payload.version.required_columns_json,
        format_rules_json=payload.version.format_rules_json,
        sample_file_id=payload.version.sample_file_id,
        created_by=payload.version.created_by,
    )
    db.add(parent)
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    return _journal_template_to_response(parent, version)


def list_journal_templates(
    db: Session, company_id: str | None = None
) -> list[CompanyJournalTemplateResponse]:
    query = db.query(CompanyJournalTemplate)
    if company_id is not None:
        query = query.filter(CompanyJournalTemplate.company_id == company_id)
    out: list[CompanyJournalTemplateResponse] = []
    for parent in query.all():
        latest = (
            db.query(CompanyJournalTemplateVersion)
            .filter(CompanyJournalTemplateVersion.company_journal_template_id == parent.id)
            .order_by(CompanyJournalTemplateVersion.version_no.desc())
            .first()
        )
        out.append(_journal_template_to_response(parent, latest))
    return out


def _bank_template_to_response(
    parent: BankTemplate, version: BankTemplateVersion | None
) -> BankTemplateResponse:
    return BankTemplateResponse(
        id=parent.id,
        company_id=parent.company_id,
        name=parent.name,
        bank_name=parent.bank_name,
        bank_account_id=parent.bank_account_id,
        status=parent.status,
        latest_version=_bank_template_version_to_response(version),
    )


def _bank_template_version_to_response(
    version: BankTemplateVersion | None,
) -> BankTemplateVersionResponse:
    return BankTemplateVersionResponse(
        version_no=version.version_no,
        file_type=version.file_type,
        sheet_selector_json=version.sheet_selector_json,
        header_row_index=version.header_row_index,
        data_start_row_index=version.data_start_row_index,
        field_aliases_json=version.field_aliases_json,
        date_formats_json=version.date_formats_json,
        amount_mode=version.amount_mode,
        amount_config_json=version.amount_config_json,
        unique_key_config_json=version.unique_key_config_json,
        sample_file_id=version.sample_file_id,
        created_by=version.created_by,
    )


def _journal_template_to_response(
    parent: CompanyJournalTemplate, version: CompanyJournalTemplateVersion | None
) -> CompanyJournalTemplateResponse:
    return CompanyJournalTemplateResponse(
        id=parent.id,
        company_id=parent.company_id,
        name=parent.name,
        status=parent.status,
        latest_version=_journal_template_version_to_response(version),
    )


def _journal_template_version_to_response(
    version: CompanyJournalTemplateVersion | None,
) -> CompanyJournalTemplateVersionResponse:
    return CompanyJournalTemplateVersionResponse(
        version_no=version.version_no,
        file_type=version.file_type,
        sheet_name=version.sheet_name,
        header_row_index=version.header_row_index,
        data_start_row_index=version.data_start_row_index,
        columns_json=version.columns_json,
        required_columns_json=version.required_columns_json,
        format_rules_json=version.format_rules_json,
        sample_file_id=version.sample_file_id,
        created_by=version.created_by,
    )
