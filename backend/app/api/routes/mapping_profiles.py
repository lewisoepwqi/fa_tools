import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.models.mapping import MappingProfile, MappingProfileVersion
from app.schemas.mapping import (
    MappingProfileCreate,
    MappingProfileResponse,
    MappingProfileVersionResponse,
)

router = APIRouter(prefix="/api/mapping-profiles", tags=["mapping-profiles"])


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
    return _to_response(parent, version)


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
