from typing import Any

from pydantic import BaseModel


class RuleVersionCreate(BaseModel):
    priority: int | None = None
    conditions_json: dict[str, Any] | None = None
    actions_json: dict[str, Any] | None = None
    allow_auto_confirm: bool = False
    created_by: str | None = None


class RuleVersionResponse(RuleVersionCreate):
    version_no: int
    # 展示名（联表解析，供前端直接显示，避免裸 ID）
    created_by_name: str | None = None


class RuleCreate(BaseModel):
    company_id: str
    name: str
    scope_type: str | None = None
    scope_id: str | None = None
    version: RuleVersionCreate


class RuleResponse(BaseModel):
    id: str
    company_id: str
    company_name: str | None = None
    name: str
    scope_type: str | None = None
    scope_id: str | None = None
    # 展示名：按 scope_type 联表解析（company→公司名，bank_template→模板名，全局→null）
    scope_name: str | None = None
    status: str
    latest_version: RuleVersionResponse
