import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from sqlalchemy import func

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    accessible_company_filter,
    require,
    require_company_access,
)
from app.core.enums import RecordStatus
from app.core.permissions import Permission
from app.models.company import Company
from app.models.user import User
from app.services.audit_service import audit_ctx, record_audit_event
from app.tools.bank_journal.models.conversion import ConversionRun
from app.tools.bank_journal.models.mapping import MappingProfile, MappingProfileVersion
from app.tools.bank_journal.models.template import (
    BankTemplateVersion,
    CompanyJournalTemplateVersion,
)
from app.tools.bank_journal.schemas.mapping import (
    MappingProfileCreate,
    MappingProfileResponse,
    MappingProfileVersionCreate,
    MappingProfileVersionResponse,
)
from app.tools.bank_journal.schemas.pagination import Page

router = APIRouter(
    prefix="/api/tools/bank-journal/mapping-profiles", tags=["mapping-profiles"]
)


@router.post(
    "",
    response_model=MappingProfileResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_mapping_profile(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    payload: MappingProfileCreate,
) -> MappingProfileResponse:
    require_company_access(user, payload.company_id)
    payload.version.created_by = user.id
    profile_id = str(uuid.uuid4())
    parent = MappingProfile(
        id=profile_id,
        company_id=payload.company_id,
        name=payload.name,
        bank_template_id=payload.bank_template_id,
        company_journal_template_id=payload.company_journal_template_id,
        status="active",
    )
    version = MappingProfileVersion(
        id=str(uuid.uuid4()),
        mapping_profile_id=profile_id,
        version_no=1,
        bank_template_version_id=payload.version.bank_template_version_id,
        company_journal_template_version_id=payload.version.company_journal_template_version_id,
        mappings_json=payload.version.mappings_json,
        created_by=payload.version.created_by,
    )
    db.add(parent)
    db.flush()  # mapping_profiles 先落库，version 的外键引用方有效
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    response = _to_response(db, parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action="mapping_profile.created",
        entity_type="mapping_profile",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.get(
    "",
    response_model=Page[MappingProfileResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_mapping_profiles(
    db: DbSession,
    user: CurrentUserDep,
    company_id: str | None = None,
    bank_template_id: str | None = None,
    company_journal_template_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[MappingProfileResponse]:
    """列表（分页）。

    可选过滤：company_id / bank_template_id / company_journal_template_id。
    后两者用于模板详情页展示"被哪些映射方案引用"（解耦后的反向关联视图）。
    """
    query = db.query(MappingProfile)
    if company_id is not None:
        query = query.filter(MappingProfile.company_id == company_id)
    # 租户收窄：accessible 非 None 时仅返回可访问公司的行
    accessible = accessible_company_filter(user)
    if accessible is not None:
        query = query.filter(MappingProfile.company_id.in_(accessible))
    if bank_template_id is not None:
        query = query.filter(MappingProfile.bank_template_id == bank_template_id)
    if company_journal_template_id is not None:
        query = query.filter(
            MappingProfile.company_journal_template_id == company_journal_template_id
        )
    # 软删除项不在列表/下拉中展示
    query = query.filter(MappingProfile.status != RecordStatus.DELETED.value)
    total = query.count()
    parents = (
        query.order_by(MappingProfile.created_at.desc(), MappingProfile.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    if not parents:
        return Page[MappingProfileResponse](items=[], total=total, limit=limit, offset=offset)
    parent_ids = [p.id for p in parents]
    latest_no = (
        db.query(
            MappingProfileVersion.mapping_profile_id.label("pid"),
            func.max(MappingProfileVersion.version_no).label("mv"),
        )
        .filter(MappingProfileVersion.mapping_profile_id.in_(parent_ids))
        .group_by(MappingProfileVersion.mapping_profile_id)
        .subquery()
    )
    versions = (
        db.query(MappingProfileVersion)
        .join(
            latest_no,
            (MappingProfileVersion.mapping_profile_id == latest_no.c.pid)
            & (MappingProfileVersion.version_no == latest_no.c.mv),
        )
        .all()
    )
    by_parent = {v.mapping_profile_id: v for v in versions}
    return Page[MappingProfileResponse](
        items=[_to_response(db, p, by_parent.get(p.id)) for p in parents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{profile_id}",
    response_model=MappingProfileResponse,
    dependencies=[Depends(require(Permission.READ))],
)
def get_mapping_profile(
    db: DbSession, user: CurrentUserDep, profile_id: str
) -> MappingProfileResponse:
    """映射方案详情（含最新版本）。不存在则 404，无权访问则 403。"""
    parent = _get_mapping_profile_or_404(db, profile_id)
    require_company_access(user, parent.company_id)  # 跨公司读取拦截
    latest = _latest_mapping_version(db, profile_id)
    return _to_response(db, parent, latest)


@router.post(
    "/{profile_id}/versions",
    response_model=MappingProfileResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_mapping_profile_version(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    profile_id: str,
    payload: MappingProfileVersionCreate,
) -> MappingProfileResponse:
    """编辑映射方案=创建新版本（旧版本不可变）。"""
    parent = _get_mapping_profile_or_404(db, profile_id)
    require_company_access(user, parent.company_id)
    payload.created_by = user.id
    before_latest = _latest_mapping_version(db, profile_id)
    new_version_no = (before_latest.version_no + 1) if before_latest else 1
    version = MappingProfileVersion(
        id=str(uuid.uuid4()),
        mapping_profile_id=profile_id,
        version_no=new_version_no,
        bank_template_version_id=payload.bank_template_version_id,
        company_journal_template_version_id=payload.company_journal_template_version_id,
        mappings_json=payload.mappings_json,
        created_by=payload.created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    response = _to_response(db, parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action="mapping_profile.modified",
        entity_type="mapping_profile",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.get(
    "/{profile_id}/versions",
    response_model=list[MappingProfileVersionResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_mapping_profile_versions(
    db: DbSession, user: CurrentUserDep, profile_id: str
) -> list[MappingProfileVersionResponse]:
    """映射方案版本历史。不存在则 404，无权访问则 403。"""
    parent = _get_mapping_profile_or_404(db, profile_id)
    require_company_access(user, parent.company_id)  # 跨公司读取拦截
    versions = (
        db.query(MappingProfileVersion)
        .filter(MappingProfileVersion.mapping_profile_id == profile_id)
        .order_by(MappingProfileVersion.version_no.desc())
        .all()
    )
    return [_version_to_response(db, version) for version in versions]


@router.patch(
    "/{profile_id}/status",
    response_model=MappingProfileResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def update_mapping_profile_status(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    profile_id: str,
    status: str,
) -> MappingProfileResponse:
    """停用/启用映射方案。校验直接在路由层做（无 service 包装）。"""
    if status not in {RecordStatus.ACTIVE.value, RecordStatus.INACTIVE.value}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {status}",
        )
    parent = _get_mapping_profile_or_404(db, profile_id)
    require_company_access(user, parent.company_id)
    parent.status = status
    db.commit()
    db.refresh(parent)
    latest = _latest_mapping_version(db, profile_id)
    response = _to_response(db, parent, latest)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=user.id,
        action=(
            "mapping_profile.disabled"
            if response.status == "inactive"
            else "mapping_profile.enabled"
        ),
        entity_type="mapping_profile",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.delete(
    "/{profile_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def delete_mapping_profile(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    profile_id: str,
) -> None:
    """软删除映射方案（status→deleted）。引用拦截：被 ConversionRun 引用则 409。"""
    parent = _get_mapping_profile_or_404(db, profile_id)
    require_company_access(user, parent.company_id)

    version_ids = [
        v.id
        for v in db.query(MappingProfileVersion.id)
        .filter(MappingProfileVersion.mapping_profile_id == profile_id)
        .all()
    ]
    run_count = (
        db.query(ConversionRun)
        .filter(ConversionRun.mapping_profile_version_id.in_(version_ids))
        .count()
        if version_ids
        else 0
    )
    if run_count > 0:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"该映射方案已被 {run_count} 个转换批次引用，无法删除（需保留历史可追溯）。",
        )

    before = _to_response(db, parent, _latest_mapping_version(db, profile_id))
    parent.status = RecordStatus.DELETED.value
    db.commit()
    db.refresh(parent)
    record_audit_event(
        db,
        company_id=parent.company_id,
        actor_id=user.id,
        action="mapping_profile.deleted",
        entity_type="mapping_profile",
        entity_id=profile_id,
        before=before.model_dump(),
        **audit_ctx(request),
    )


def _get_mapping_profile_or_404(db: DbSession, profile_id: str) -> MappingProfile:
    parent = db.query(MappingProfile).filter(MappingProfile.id == profile_id).first()
    if parent is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Mapping profile not found: {profile_id}",
        )
    return parent


def _latest_mapping_version(db: DbSession, profile_id: str) -> MappingProfileVersion | None:
    return (
        db.query(MappingProfileVersion)
        .filter(MappingProfileVersion.mapping_profile_id == profile_id)
        .order_by(MappingProfileVersion.version_no.desc())
        .first()
    )


def _version_to_response(
    db: DbSession, version: MappingProfileVersion
) -> MappingProfileVersionResponse:
    return MappingProfileVersionResponse(
        version_no=version.version_no,
        bank_template_version_id=version.bank_template_version_id,
        company_journal_template_version_id=version.company_journal_template_version_id,
        mappings_json=version.mappings_json,
        created_by=version.created_by,
        created_by_name=_user_name(db, version.created_by),
        bank_template_version_no=_template_version_no(
            db, BankTemplateVersion, version.bank_template_version_id
        ),
        company_journal_template_version_no=_template_version_no(
            db, CompanyJournalTemplateVersion, version.company_journal_template_version_id
        ),
    )


def _to_response(
    db: DbSession, parent: MappingProfile, version: MappingProfileVersion | None
) -> MappingProfileResponse:
    return MappingProfileResponse(
        id=parent.id,
        company_id=parent.company_id,
        company_name=_company_name(db, parent.company_id),
        name=parent.name,
        bank_template_id=parent.bank_template_id,
        company_journal_template_id=parent.company_journal_template_id,
        status=parent.status,
        latest_version=MappingProfileVersionResponse(
            version_no=version.version_no,
            bank_template_version_id=version.bank_template_version_id,
            company_journal_template_version_id=version.company_journal_template_version_id,
            mappings_json=version.mappings_json,
            created_by=version.created_by,
            created_by_name=_user_name(db, version.created_by),
            bank_template_version_no=_template_version_no(
                db, BankTemplateVersion, version.bank_template_version_id
            ),
            company_journal_template_version_no=_template_version_no(
                db, CompanyJournalTemplateVersion, version.company_journal_template_version_id
            ),
        ),
    )


def _company_name(db: DbSession, company_id: str | None) -> str | None:
    if not company_id:
        return None
    c = db.get(Company, company_id)
    return c.name if c else None


def _user_name(db: DbSession, user_id: str | None) -> str | None:
    if not user_id:
        return None
    u = db.get(User, user_id)
    if u is None:
        return None
    return u.name or u.email


def _template_version_no(db: DbSession, model, version_id: str | None) -> int | None:
    """按版本 id 查 version_no（避免裸 UUID）。model 为版本表 ORM 类。"""
    if not version_id:
        return None
    v = db.get(model, version_id)
    return v.version_no if v else None
