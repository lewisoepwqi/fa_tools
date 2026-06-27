import uuid

from fastapi import APIRouter

from app.schemas.mapping import (
    MappingProfileCreate,
    MappingProfileResponse,
    MappingProfileVersionResponse,
)

router = APIRouter(prefix="/api/mapping-profiles", tags=["mapping-profiles"])

_mapping_profiles: dict[str, MappingProfileResponse] = {}


@router.post("", response_model=MappingProfileResponse)
def create_mapping_profile(payload: MappingProfileCreate) -> MappingProfileResponse:
    profile_id = str(uuid.uuid4())
    response = MappingProfileResponse(
        id=profile_id,
        company_id=payload.company_id,
        name=payload.name,
        bank_template_id=payload.bank_template_id,
        company_journal_template_id=payload.company_journal_template_id,
        status="active",
        latest_version=MappingProfileVersionResponse(version_no=1, **payload.version.model_dump()),
    )
    _mapping_profiles[profile_id] = response
    return response


@router.get("", response_model=list[MappingProfileResponse])
def list_mapping_profiles(company_id: str | None = None) -> list[MappingProfileResponse]:
    profiles = list(_mapping_profiles.values())
    if company_id is not None:
        profiles = [p for p in profiles if p.company_id == company_id]
    return profiles
