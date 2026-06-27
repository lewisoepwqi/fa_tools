import uuid

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from app.api.deps import DbSession
from app.core.enums import RecordStatus
from app.services.audit_service import record_audit_event
from app.tools.bank_journal.models.mapping import MappingProfile, MappingProfileVersion
from app.tools.bank_journal.schemas.mapping import (
    MappingProfileCreate,
    MappingProfileResponse,
    MappingProfileVersionCreate,
    MappingProfileVersionResponse,
)

router = APIRouter(
    prefix="/api/tools/bank-journal/mapping-profiles", tags=["mapping-profiles"]
)


@router.post("", response_model=MappingProfileResponse)
def create_mapping_profile(
    db: DbSession, payload: MappingProfileCreate
) -> MappingProfileResponse:
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
    db.add(version)
    db.commit()
    db.refresh(parent)
    db.refresh(version)
    response = _to_response(parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="mapping_profile.created",
        entity_type="mapping_profile",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get("", response_model=list[MappingProfileResponse])
def list_mapping_profiles(
    db: DbSession, company_id: str | None = None
) -> list[MappingProfileResponse]:
    query = db.query(MappingProfile)
    if company_id is not None:
        query = query.filter(MappingProfile.company_id == company_id)
    out: list[MappingProfileResponse] = []
    for parent in query.all():
        latest = (
            db.query(MappingProfileVersion)
            .filter(MappingProfileVersion.mapping_profile_id == parent.id)
            .order_by(MappingProfileVersion.version_no.desc())
            .first()
        )
        out.append(_to_response(parent, latest))
    return out


@router.get("/{profile_id}", response_model=MappingProfileResponse)
def get_mapping_profile(db: DbSession, profile_id: str) -> MappingProfileResponse:
    """映射方案详情（含最新版本）。不存在则 404。"""
    parent = _get_mapping_profile_or_404(db, profile_id)
    latest = _latest_mapping_version(db, profile_id)
    return _to_response(parent, latest)


@router.post("/{profile_id}/versions", response_model=MappingProfileResponse)
def create_mapping_profile_version(
    db: DbSession, profile_id: str, payload: MappingProfileVersionCreate
) -> MappingProfileResponse:
    """编辑映射方案=创建新版本（旧版本不可变）。"""
    parent = _get_mapping_profile_or_404(db, profile_id)
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
    response = _to_response(parent, version)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=response.latest_version.created_by,
        action="mapping_profile.modified",
        entity_type="mapping_profile",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get(
    "/{profile_id}/versions", response_model=list[MappingProfileVersionResponse]
)
def list_mapping_profile_versions(
    db: DbSession, profile_id: str
) -> list[MappingProfileVersionResponse]:
    """映射方案版本历史。"""
    _get_mapping_profile_or_404(db, profile_id)
    versions = (
        db.query(MappingProfileVersion)
        .filter(MappingProfileVersion.mapping_profile_id == profile_id)
        .order_by(MappingProfileVersion.version_no.desc())
        .all()
    )
    return [_version_to_response(version) for version in versions]


@router.patch("/{profile_id}/status", response_model=MappingProfileResponse)
def update_mapping_profile_status(
    db: DbSession, profile_id: str, status: str
) -> MappingProfileResponse:
    """停用/启用映射方案。校验直接在路由层做（无 service 包装）。"""
    if status not in {RecordStatus.ACTIVE.value, RecordStatus.INACTIVE.value}:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {status}",
        )
    parent = _get_mapping_profile_or_404(db, profile_id)
    parent.status = status
    db.commit()
    db.refresh(parent)
    latest = _latest_mapping_version(db, profile_id)
    response = _to_response(parent, latest)
    record_audit_event(
        db,
        company_id=response.company_id,
        actor_id=None,
        action=(
            "mapping_profile.disabled"
            if response.status == "inactive"
            else "mapping_profile.enabled"
        ),
        entity_type="mapping_profile",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


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


def _version_to_response(version: MappingProfileVersion) -> MappingProfileVersionResponse:
    return MappingProfileVersionResponse(
        version_no=version.version_no,
        bank_template_version_id=version.bank_template_version_id,
        company_journal_template_version_id=version.company_journal_template_version_id,
        mappings_json=version.mappings_json,
        created_by=version.created_by,
    )


def _to_response(
    parent: MappingProfile, version: MappingProfileVersion | None
) -> MappingProfileResponse:
    return MappingProfileResponse(
        id=parent.id,
        company_id=parent.company_id,
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
        ),
    )
