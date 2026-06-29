from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    require,
    require_company_access,
)
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event
from app.tools.bank_journal.models.conversion import ConversionRun
from app.tools.bank_journal.models.mapping import MappingProfile
from app.tools.bank_journal.models.template import CompanyJournalTemplateVersion
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


@router.post(
    "",
    response_model=CompanyJournalTemplateResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_journal_template(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    payload: CompanyJournalTemplateCreate,
) -> CompanyJournalTemplateResponse:
    require_company_access(user, payload.company_id)
    payload.version.created_by = user.id
    response = template_service.create_journal_template(db, payload)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action="journal_template.created",
        entity_type="company_journal_template",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.get(
    "",
    response_model=list[CompanyJournalTemplateResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_journal_templates(
    db: DbSession, company_id: str | None = None
) -> list[CompanyJournalTemplateResponse]:
    return template_service.list_journal_templates(db, company_id)


@router.get(
    "/{template_id}",
    response_model=CompanyJournalTemplateResponse,
    dependencies=[Depends(require(Permission.READ))],
)
def get_journal_template(
    db: DbSession, template_id: str
) -> CompanyJournalTemplateResponse:
    """日记账模板详情（含最新版本）。不存在则 404。"""
    return template_service.get_journal_template(db, template_id)


@router.post(
    "/{template_id}/versions",
    response_model=CompanyJournalTemplateResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_journal_template_version(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    template_id: str,
    payload: CompanyJournalTemplateVersionCreate,
) -> CompanyJournalTemplateResponse:
    """编辑日记账模板=创建新版本。"""
    before = template_service.get_journal_template(db, template_id)
    require_company_access(user, before.company_id)
    payload.created_by = user.id
    response = template_service.create_journal_template_version(db, template_id, payload)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action="journal_template.modified",
        entity_type="company_journal_template",
        entity_id=response.id,
        before=before.model_dump(),
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.get(
    "/{template_id}/versions",
    response_model=list[CompanyJournalTemplateVersionResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_journal_template_versions(
    db: DbSession, template_id: str
) -> list[CompanyJournalTemplateVersionResponse]:
    """日记账模板版本历史。"""
    return template_service.list_journal_template_versions(db, template_id)


@router.patch(
    "/{template_id}/status",
    response_model=CompanyJournalTemplateResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def update_journal_template_status(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    template_id: str,
    status: str,
) -> CompanyJournalTemplateResponse:
    """停用/启用日记账模板。校验委托服务层。"""
    before = template_service.get_journal_template(db, template_id)
    require_company_access(user, before.company_id)
    response = template_service.set_journal_template_status(db, template_id, status)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action=(
            "journal_template.disabled"
            if response.status == "inactive"
            else "journal_template.enabled"
        ),
        entity_type="company_journal_template",
        entity_id=response.id,
        before=before.model_dump(),
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def delete_journal_template(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    template_id: str,
) -> None:
    """软删除日记账模板（status→deleted）。引用拦截同银行模板。"""
    parent = template_service.get_journal_template(db, template_id)
    require_company_access(user, parent.company_id)

    version_ids = [
        v.id
        for v in db.query(CompanyJournalTemplateVersion.id)
        .filter(CompanyJournalTemplateVersion.company_journal_template_id == template_id)
        .all()
    ]
    run_count = (
        db.query(ConversionRun)
        .filter(ConversionRun.company_journal_template_version_id.in_(version_ids))
        .count()
        if version_ids
        else 0
    )
    if run_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该日记账模板已被 {run_count} 个转换批次引用，无法删除（需保留历史可追溯）。",
        )
    mapping_count = (
        db.query(MappingProfile)
        .filter(MappingProfile.company_journal_template_id == template_id)
        .filter(MappingProfile.status != "deleted")
        .count()
    )
    if mapping_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该日记账模板被 {mapping_count} 个映射方案引用，请先删除或解绑相关映射方案。",
        )

    before = template_service.get_journal_template(db, template_id)
    parent_entity = template_service.soft_delete_journal_template(db, template_id)
    record_audit_event(
        db,
        company_id=parent_entity.company_id,
        actor_id=user.id,
        action="journal_template.deleted",
        entity_type="company_journal_template",
        entity_id=template_id,
        before=before.model_dump(),
        **audit_ctx(request),
    )
