"""公司级自定义扩展字段的 HTTP 路由。"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    accessible_company_filter,
    require,
    require_company_access,
)
from app.core.permissions import Permission
from app.tools.bank_journal.models.custom_field import CustomField
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


@router.get(
    "/standard-schema",
    response_model=StandardSchemaResponse,
    dependencies=[Depends(require(Permission.READ))],
)
def get_standard_schema(
    db: DbSession, user: CurrentUserDep, company_id: str
) -> StandardSchemaResponse:
    """返回内置标准字段（含公司覆盖）+ 公司扩展字段的合并视图，供前端字段下拉运行时拉取。"""
    require_company_access(user, company_id)  # 跨公司读取拦截
    return custom_field_service.get_standard_schema(db, company_id)


@router.get(
    "",
    response_model=list[CustomFieldResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_custom_fields(
    db: DbSession, user: CurrentUserDep, company_id: str | None = None
) -> list[CustomFieldResponse]:
    return custom_field_service.list_custom_fields(
        db, company_id, accessible=accessible_company_filter(user)
    )


@router.post(
    "",
    response_model=CustomFieldResponse,
    status_code=201,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def create_custom_field(
    db: DbSession, user: CurrentUserDep, payload: CustomFieldCreate
) -> CustomFieldResponse:
    require_company_access(user, payload.company_id)
    payload.created_by = user.id
    return custom_field_service.create_custom_field(db, payload)


@router.patch(
    "/{field_id}",
    response_model=CustomFieldResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def update_custom_field(
    db: DbSession, user: CurrentUserDep, field_id: str, payload: CustomFieldUpdate
) -> CustomFieldResponse:
    _require_field_company_access(db, user, field_id)
    return custom_field_service.update_custom_field(db, field_id, payload)


@router.delete(
    "/{field_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def delete_custom_field(db: DbSession, user: CurrentUserDep, field_id: str) -> None:
    _require_field_company_access(db, user, field_id)
    custom_field_service.delete_custom_field(db, field_id)


def _require_field_company_access(db: DbSession, user: CurrentUserDep, field_id: str) -> None:
    """加载扩展字段并按其公司做写访问校验（不存在则保持 404 由 service 抛出）。"""
    cf = db.query(CustomField).filter(CustomField.id == field_id).first()
    if cf is None:
        return  # 交由 service 层 _get_or_404 抛 404，避免把 404 变 403
    require_company_access(user, cf.company_id)


# ---------------------------------------------------------------------------
# 内置字段覆盖（公司级：label / 识别关键词 / 规则类型）
# ---------------------------------------------------------------------------


@router.get(
    "/builtin-overrides",
    response_model=list[BuiltinFieldOverrideResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_builtin_overrides(
    db: DbSession, user: CurrentUserDep, company_id: str
) -> list[BuiltinFieldOverrideResponse]:
    require_company_access(user, company_id)  # 跨公司读取拦截
    return custom_field_service.list_builtin_overrides(db, company_id)


@router.put(
    "/builtin-overrides/{field_key}",
    response_model=BuiltinFieldOverrideResponse,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def upsert_builtin_override(
    db: DbSession,
    user: CurrentUserDep,
    field_key: str,
    payload: BuiltinFieldOverrideUpsert,
) -> BuiltinFieldOverrideResponse:
    require_company_access(user, payload.company_id)
    # path 参数与 body 的 field_key 必须一致
    payload.field_key = field_key
    return custom_field_service.upsert_builtin_override(db, payload)


@router.delete(
    "/builtin-overrides/{field_key}",
    status_code=204,
    dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))],
)
def delete_builtin_override(
    db: DbSession, user: CurrentUserDep, field_key: str, company_id: str
) -> None:
    require_company_access(user, company_id)
    custom_field_service.delete_builtin_override(db, company_id, field_key)
