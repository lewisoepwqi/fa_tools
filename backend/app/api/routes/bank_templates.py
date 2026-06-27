from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.file import SourceFile
from app.schemas.template import (
    BankTemplateCreate,
    BankTemplateDetectRequest,
    BankTemplateDetectResponse,
    BankTemplateResponse,
    BankTemplateVersionCreate,
    BankTemplateVersionResponse,
)
from app.services import template_service
from app.services.audit_service import record_audit_event
from app.services.parser_service import detect_bank_template_config

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


@router.post("/detect", response_model=BankTemplateDetectResponse)
def detect_bank_template(
    db: DbSession, payload: BankTemplateDetectRequest
) -> BankTemplateDetectResponse:
    """从已上传的样本文件自动识别银行模板配置（PRD §5.1）。"""
    source = db.query(SourceFile).filter(SourceFile.id == payload.source_file_id).first()
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source file not found: {payload.source_file_id}",
        )
    file_path = Path(get_settings().upload_dir) / source.storage_key
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source file not found on disk",
        )
    detected = detect_bank_template_config(
        file_path, source.file_type, payload.sheet_name or ""
    )
    return BankTemplateDetectResponse(**detected)


@router.get("", response_model=list[BankTemplateResponse])
def list_bank_templates(
    db: DbSession, company_id: str | None = None
) -> list[BankTemplateResponse]:
    return template_service.list_bank_templates(db, company_id)


@router.get("/{template_id}", response_model=BankTemplateResponse)
def get_bank_template(db: DbSession, template_id: str) -> BankTemplateResponse:
    """银行模板详情（含最新版本）。不存在则 404。"""
    return template_service.get_bank_template(db, template_id)


@router.post("/{template_id}/versions", response_model=BankTemplateResponse)
def create_bank_template_version(
    db: DbSession, template_id: str, payload: BankTemplateVersionCreate
) -> BankTemplateResponse:
    """编辑银行模板=创建新版本（旧版本不可变，历史批次仍引用旧版本）。"""
    before = template_service.get_bank_template(db, template_id)
    response = template_service.create_bank_template_version(db, template_id, payload)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="bank_template.modified",
        entity_type="bank_template",
        entity_id=response.id,
        before=before.model_dump(),
        after=response.model_dump(),
    )
    return response


@router.get(
    "/{template_id}/versions", response_model=list[BankTemplateVersionResponse]
)
def list_bank_template_versions(
    db: DbSession, template_id: str
) -> list[BankTemplateVersionResponse]:
    """银行模板版本历史。"""
    return template_service.list_bank_template_versions(db, template_id)


@router.patch("/{template_id}/status", response_model=BankTemplateResponse)
def update_bank_template_status(
    db: DbSession, template_id: str, status: str
) -> BankTemplateResponse:
    """停用/启用银行模板（status: active|inactive）。校验委托服务层。"""
    before = template_service.get_bank_template(db, template_id)
    response = template_service.set_bank_template_status(db, template_id, status)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=None,
        action=(
            "bank_template.disabled"
            if response.status == "inactive"
            else "bank_template.enabled"
        ),
        entity_type="bank_template",
        entity_id=response.id,
        before=before.model_dump(),
        after=response.model_dump(),
    )
    return response
