from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.file import SourceFile
from app.services.audit_service import record_audit_event
from app.tools.bank_journal.models.conversion import ConversionRun
from app.tools.bank_journal.models.mapping import MappingProfile
from app.tools.bank_journal.models.template import BankTemplateVersion
from app.tools.bank_journal.schemas.template import (
    BankTemplateCreate,
    BankTemplateDetectRequest,
    BankTemplateDetectResponse,
    BankTemplateResponse,
    BankTemplateVersionCreate,
    BankTemplateVersionResponse,
)
from app.tools.bank_journal.services import template_service
from app.tools.bank_journal.services.custom_field_service import (
    load_builtin_keyword_overrides,
    load_custom_field_defs,
)
from app.tools.bank_journal.services.parser_service import (
    CustomFieldDef,
    detect_bank_template_config,
)

router = APIRouter(
    prefix="/api/tools/bank-journal/bank-templates", tags=["bank-templates"]
)


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
    # 加载公司级扩展字段，detect 时一并识别其表头关键词
    custom_defs: list[CustomFieldDef] = []
    builtin_kw_overrides: dict[str, list[str]] = {}
    if payload.company_id:
        custom_defs = load_custom_field_defs(db, payload.company_id)
        builtin_kw_overrides = load_builtin_keyword_overrides(db, payload.company_id)
    detected = detect_bank_template_config(
        file_path,
        source.file_type,
        payload.sheet_name or "",
        custom_defs,
        builtin_kw_overrides,
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


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_template(db: DbSession, template_id: str) -> None:
    """软删除银行模板（status→deleted）。

    引用拦截（保证历史批次可追溯，PRD §10.3.3）：
    - 该模板任一版本被 ConversionRun 引用 → 409
    - 该模板被任一映射方案引用 → 409（提示先处理映射方案）
    无引用时软删除（保留行与版本，仅置 deleted）。
    """
    parent = template_service.get_bank_template(db, template_id)

    version_ids = [
        v.id
        for v in db.query(BankTemplateVersion.id)
        .filter(BankTemplateVersion.bank_template_id == template_id)
        .all()
    ]
    run_count = (
        db.query(ConversionRun)
        .filter(ConversionRun.bank_template_version_id.in_(version_ids))
        .count()
        if version_ids
        else 0
    )
    if run_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该银行模板已被 {run_count} 个转换批次引用，无法删除（需保留历史可追溯）。",
        )
    mapping_count = (
        db.query(MappingProfile)
        .filter(MappingProfile.bank_template_id == template_id)
        .filter(MappingProfile.status != "deleted")
        .count()
    )
    if mapping_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该银行模板被 {mapping_count} 个映射方案引用，请先删除或解绑相关映射方案。",
        )

    before = parent.model_copy(deep=True)
    parent_entity = template_service.soft_delete_bank_template(db, template_id)
    record_audit_event(
        db,
        company_id=parent_entity.company_id,
        actor_id=None,
        action="bank_template.deleted",
        entity_type="bank_template",
        entity_id=template_id,
        before=before.model_dump(),
    )
