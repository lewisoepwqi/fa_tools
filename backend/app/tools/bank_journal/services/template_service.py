from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import RecordStatus
from app.tools.bank_journal.models.template import (
    BankTemplate,
    BankTemplateVersion,
    CompanyJournalTemplate,
    CompanyJournalTemplateVersion,
)
from app.tools.bank_journal.schemas.template import (
    BankTemplateCreate,
    BankTemplateResponse,
    BankTemplateVersionCreate,
    BankTemplateVersionResponse,
    CompanyJournalTemplateCreate,
    CompanyJournalTemplateResponse,
    CompanyJournalTemplateVersionCreate,
    CompanyJournalTemplateVersionResponse,
)

ALLOWED_STATUSES = {RecordStatus.ACTIVE.value, RecordStatus.INACTIVE.value}


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
    db.flush()  # bank_templates 先落库，version 的外键引用方有效
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    return _bank_template_to_response(parent, version)


def list_bank_templates(db: Session, company_id: str | None = None) -> list[BankTemplateResponse]:
    query = db.query(BankTemplate)
    if company_id is not None:
        query = query.filter(BankTemplate.company_id == company_id)
    # 软删除项不在列表/下拉中展示（删除仅置 status=deleted，行与版本保留）
    query = query.filter(BankTemplate.status != RecordStatus.DELETED.value)
    parents = query.all()
    if not parents:
        return []
    parent_ids = [p.id for p in parents]
    latest_no = (
        db.query(
            BankTemplateVersion.bank_template_id.label("pid"),
            func.max(BankTemplateVersion.version_no).label("mv"),
        )
        .filter(BankTemplateVersion.bank_template_id.in_(parent_ids))
        .group_by(BankTemplateVersion.bank_template_id)
        .subquery()
    )
    versions = (
        db.query(BankTemplateVersion)
        .join(
            latest_no,
            (BankTemplateVersion.bank_template_id == latest_no.c.pid)
            & (BankTemplateVersion.version_no == latest_no.c.mv),
        )
        .all()
    )
    by_parent = {v.bank_template_id: v for v in versions}
    return [_bank_template_to_response(p, by_parent.get(p.id)) for p in parents]


def get_bank_template(db: Session, template_id: str) -> BankTemplateResponse:
    """按 id 加载银行模板（含最新版本）。不存在则 404。"""
    parent = _get_bank_template_or_404(db, template_id)
    latest = _latest_bank_template_version(db, template_id)
    return _bank_template_to_response(parent, latest)


def soft_delete_bank_template(db: Session, template_id: str):
    """软删除银行模板（status→deleted）。引用拦截由路由层负责。返回父实体供审计。"""
    parent = _get_bank_template_or_404(db, template_id)
    parent.status = RecordStatus.DELETED.value
    db.commit()
    db.refresh(parent)
    return parent


def create_bank_template_version(
    db: Session, template_id: str, payload: BankTemplateVersionCreate
) -> BankTemplateResponse:
    """编辑=创建新版本（PRD §6.2 / 技术设计 §8.1）。旧版本数据不动。"""
    parent = _get_bank_template_or_404(db, template_id)
    latest = _latest_bank_template_version(db, template_id)
    new_version_no = (latest.version_no + 1) if latest else 1
    version = BankTemplateVersion(
        id=str(uuid.uuid4()),
        bank_template_id=template_id,
        version_no=new_version_no,
        file_type=payload.file_type,
        sheet_selector_json=payload.sheet_selector_json,
        header_row_index=payload.header_row_index,
        data_start_row_index=payload.data_start_row_index,
        field_aliases_json=payload.field_aliases_json,
        date_formats_json=payload.date_formats_json,
        amount_mode=payload.amount_mode,
        amount_config_json=payload.amount_config_json,
        unique_key_config_json=payload.unique_key_config_json,
        sample_file_id=payload.sample_file_id,
        created_by=payload.created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    return _bank_template_to_response(parent, version)


def list_bank_template_versions(
    db: Session, template_id: str
) -> list[BankTemplateVersionResponse]:
    """银行模板版本历史（PRD §10.1.3 历史批次能查看当时使用的模板版本）。"""
    _get_bank_template_or_404(db, template_id)
    versions = (
        db.query(BankTemplateVersion)
        .filter(BankTemplateVersion.bank_template_id == template_id)
        .order_by(BankTemplateVersion.version_no.desc())
        .all()
    )
    return [_bank_template_version_to_response(version) for version in versions]


def set_bank_template_status(
    db: Session, template_id: str, new_status: str
) -> BankTemplateResponse:
    """停用/启用银行模板（PRD §6.10.3）。"""
    _validate_status(new_status)
    parent = _get_bank_template_or_404(db, template_id)
    parent.status = new_status
    db.commit()
    db.refresh(parent)
    latest = _latest_bank_template_version(db, template_id)
    return _bank_template_to_response(parent, latest)


def _get_bank_template_or_404(db: Session, template_id: str) -> BankTemplate:
    parent = db.query(BankTemplate).filter(BankTemplate.id == template_id).first()
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bank template not found: {template_id}",
        )
    return parent


def _latest_bank_template_version(
    db: Session, template_id: str
) -> BankTemplateVersion | None:
    return (
        db.query(BankTemplateVersion)
        .filter(BankTemplateVersion.bank_template_id == template_id)
        .order_by(BankTemplateVersion.version_no.desc())
        .first()
    )


def _validate_status(new_status: str) -> None:
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {new_status}. Allowed: {sorted(ALLOWED_STATUSES)}",
        )


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
    db.flush()  # company_journal_templates 先落库，version 的外键引用方有效
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
    # 软删除项不在列表/下拉中展示
    query = query.filter(CompanyJournalTemplate.status != RecordStatus.DELETED.value)
    parents = query.all()
    if not parents:
        return []
    parent_ids = [p.id for p in parents]
    latest_no = (
        db.query(
            CompanyJournalTemplateVersion.company_journal_template_id.label("pid"),
            func.max(CompanyJournalTemplateVersion.version_no).label("mv"),
        )
        .filter(CompanyJournalTemplateVersion.company_journal_template_id.in_(parent_ids))
        .group_by(CompanyJournalTemplateVersion.company_journal_template_id)
        .subquery()
    )
    versions = (
        db.query(CompanyJournalTemplateVersion)
        .join(
            latest_no,
            (CompanyJournalTemplateVersion.company_journal_template_id == latest_no.c.pid)
            & (CompanyJournalTemplateVersion.version_no == latest_no.c.mv),
        )
        .all()
    )
    by_parent = {v.company_journal_template_id: v for v in versions}
    return [_journal_template_to_response(p, by_parent.get(p.id)) for p in parents]


def get_journal_template(
    db: Session, template_id: str
) -> CompanyJournalTemplateResponse:
    """按 id 加载日记账模板（含最新版本）。不存在则 404。"""
    parent = _get_journal_template_or_404(db, template_id)
    latest = _latest_journal_template_version(db, template_id)
    return _journal_template_to_response(parent, latest)


def soft_delete_journal_template(db: Session, template_id: str):
    """软删除日记账模板（status→deleted）。引用拦截由路由层负责。返回父实体供审计。"""
    parent = _get_journal_template_or_404(db, template_id)
    parent.status = RecordStatus.DELETED.value
    db.commit()
    db.refresh(parent)
    return parent


def create_journal_template_version(
    db: Session, template_id: str, payload: CompanyJournalTemplateVersionCreate
) -> CompanyJournalTemplateResponse:
    """编辑=创建新版本（PRD §6.3 / 技术设计 §8.1）。"""
    parent = _get_journal_template_or_404(db, template_id)
    latest = _latest_journal_template_version(db, template_id)
    new_version_no = (latest.version_no + 1) if latest else 1
    version = CompanyJournalTemplateVersion(
        id=str(uuid.uuid4()),
        company_journal_template_id=template_id,
        version_no=new_version_no,
        file_type=payload.file_type,
        sheet_name=payload.sheet_name,
        header_row_index=payload.header_row_index,
        data_start_row_index=payload.data_start_row_index,
        columns_json=payload.columns_json,
        required_columns_json=payload.required_columns_json,
        format_rules_json=payload.format_rules_json,
        sample_file_id=payload.sample_file_id,
        created_by=payload.created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    return _journal_template_to_response(parent, version)


def list_journal_template_versions(
    db: Session, template_id: str
) -> list[CompanyJournalTemplateVersionResponse]:
    """日记账模板版本历史。"""
    _get_journal_template_or_404(db, template_id)
    versions = (
        db.query(CompanyJournalTemplateVersion)
        .filter(CompanyJournalTemplateVersion.company_journal_template_id == template_id)
        .order_by(CompanyJournalTemplateVersion.version_no.desc())
        .all()
    )
    return [_journal_template_version_to_response(version) for version in versions]


def set_journal_template_status(
    db: Session, template_id: str, new_status: str
) -> CompanyJournalTemplateResponse:
    """停用/启用日记账模板。"""
    _validate_status(new_status)
    parent = _get_journal_template_or_404(db, template_id)
    parent.status = new_status
    db.commit()
    db.refresh(parent)
    latest = _latest_journal_template_version(db, template_id)
    return _journal_template_to_response(parent, latest)


def _get_journal_template_or_404(
    db: Session, template_id: str
) -> CompanyJournalTemplate:
    parent = (
        db.query(CompanyJournalTemplate)
        .filter(CompanyJournalTemplate.id == template_id)
        .first()
    )
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal template not found: {template_id}",
        )
    return parent


def _latest_journal_template_version(
    db: Session, template_id: str
) -> CompanyJournalTemplateVersion | None:
    return (
        db.query(CompanyJournalTemplateVersion)
        .filter(CompanyJournalTemplateVersion.company_journal_template_id == template_id)
        .order_by(CompanyJournalTemplateVersion.version_no.desc())
        .first()
    )


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
