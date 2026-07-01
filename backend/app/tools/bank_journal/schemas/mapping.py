from typing import Any

from pydantic import BaseModel


class MappingProfileVersionCreate(BaseModel):
    bank_template_version_id: str | None = None
    company_journal_template_version_id: str | None = None
    mappings_json: dict[str, Any] | None = None
    created_by: str | None = None


class MappingProfileVersionResponse(MappingProfileVersionCreate):
    version_no: int
    # 展示名（联表解析，供前端直接显示，避免裸 ID）
    created_by_name: str | None = None
    bank_template_version_no: int | None = None
    company_journal_template_version_no: int | None = None


class MappingProfileCreate(BaseModel):
    company_id: str
    name: str
    bank_template_id: str | None = None
    company_journal_template_id: str | None = None
    version: MappingProfileVersionCreate


class MappingProfileResponse(BaseModel):
    id: str
    company_id: str
    company_name: str | None = None
    name: str
    bank_template_id: str | None = None
    company_journal_template_id: str | None = None
    status: str
    latest_version: MappingProfileVersionResponse
