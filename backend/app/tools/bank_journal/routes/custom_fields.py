"""公司级自定义扩展字段的 HTTP 路由。"""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.tools.bank_journal.schemas.custom_field import (
    BuiltinFieldOverrideResponse,
    BuiltinFieldOverrideUpsert,
    CustomFieldCreate,
    CustomFieldResponse,
    CustomFieldUpdate,
    StandardSchemaResponse,
)
from app.tools.bank_journal.services import custom_field_service

router = APIRouter(prefix="/api/tools/bank-journal/custom-fields", tags=["custom-fields"])


@router.get("/standard-schema", response_model=StandardSchemaResponse)
def get_standard_schema(db: DbSession, company_id: str) -> StandardSchemaResponse:
    """返回内置标准字段（含公司覆盖）+ 公司扩展字段的合并视图，供前端字段下拉运行时拉取。"""
    return custom_field_service.get_standard_schema(db, company_id)


@router.get("", response_model=list[CustomFieldResponse])
def list_custom_fields(
    db: DbSession, company_id: str | None = None
) -> list[CustomFieldResponse]:
    return custom_field_service.list_custom_fields(db, company_id)


@router.post("", response_model=CustomFieldResponse, status_code=201)
def create_custom_field(
    db: DbSession, payload: CustomFieldCreate
) -> CustomFieldResponse:
    return custom_field_service.create_custom_field(db, payload)


@router.patch("/{field_id}", response_model=CustomFieldResponse)
def update_custom_field(
    db: DbSession, field_id: str, payload: CustomFieldUpdate
) -> CustomFieldResponse:
    return custom_field_service.update_custom_field(db, field_id, payload)


@router.delete("/{field_id}", status_code=204)
def delete_custom_field(db: DbSession, field_id: str) -> None:
    custom_field_service.delete_custom_field(db, field_id)


# ---------------------------------------------------------------------------
# 内置字段覆盖（公司级：label / 识别关键词 / 规则类型）
# ---------------------------------------------------------------------------


@router.get("/builtin-overrides", response_model=list[BuiltinFieldOverrideResponse])
def list_builtin_overrides(
    db: DbSession, company_id: str
) -> list[BuiltinFieldOverrideResponse]:
    return custom_field_service.list_builtin_overrides(db, company_id)


@router.put("/builtin-overrides/{field_key}", response_model=BuiltinFieldOverrideResponse)
def upsert_builtin_override(
    db: DbSession, field_key: str, payload: BuiltinFieldOverrideUpsert
) -> BuiltinFieldOverrideResponse:
    # path 参数与 body 的 field_key 必须一致
    payload.field_key = field_key
    return custom_field_service.upsert_builtin_override(db, payload)


@router.delete("/builtin-overrides/{field_key}", status_code=204)
def delete_builtin_override(db: DbSession, field_key: str, company_id: str) -> None:
    custom_field_service.delete_builtin_override(db, company_id, field_key)
