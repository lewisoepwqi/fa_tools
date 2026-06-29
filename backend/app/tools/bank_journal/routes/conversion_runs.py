from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    accessible_company_filter,
    require,
    require_company_access,
)
from app.core.config import get_settings
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event
from app.tools.bank_journal.models.conversion import ConversionRun
from app.tools.bank_journal.schemas.conversion import (
    ConversionRunCreate,
    ConversionRunFromConfigCreate,
    ConversionRunListItemResponse,
    ConversionRunResponse,
    DryRunCreate,
    DryRunResponse,
    JournalPreviewRowData,
)
from app.tools.bank_journal.schemas.pagination import Page
from app.tools.bank_journal.services.conversion_service import (
    dry_run_conversion,
    get_conversion_run,
    list_conversion_runs,
    list_preview_rows,
    run_conversion,
    run_conversion_from_config,
)

router = APIRouter(
    prefix="/api/tools/bank-journal/conversion-runs", tags=["conversion-runs"]
)


@router.post(
    "",
    response_model=ConversionRunResponse,
    dependencies=[Depends(require(Permission.CONVERSION_PROCESS))],
)
def start_conversion_run(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    payload: ConversionRunCreate,
) -> ConversionRunResponse:
    require_company_access(user, payload.company_id)
    upload_dir = Path(get_settings().upload_dir)
    response = run_conversion(db, payload, upload_dir)
    record_audit_event(
        db,
        company_id=payload.company_id,
        actor_id=user.id,
        action="conversion_run.created",
        entity_type="conversion_run",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.post(
    "/from-config",
    response_model=ConversionRunResponse,
    dependencies=[Depends(require(Permission.CONVERSION_PROCESS))],
)
def start_conversion_from_config(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    payload: ConversionRunFromConfigCreate,
) -> ConversionRunResponse:
    """P0：用已配置的版本化模板/映射/规则驱动转换。

    与 ``POST /conversion-runs``（内联传 parse_config/mappings/rules）相对：本端点
    只传配置 ID，服务端从 DB 查最新版本拼装内联参数后执行同一套 parse/preview 逻辑。
    让用户在四个配置模块里配的内容真正生效。
    """
    require_company_access(user, payload.company_id)
    upload_dir = Path(get_settings().upload_dir)
    response = run_conversion_from_config(db, payload, upload_dir)
    record_audit_event(
        db,
        company_id=payload.company_id,
        actor_id=user.id,
        action="conversion_run.created_from_config",
        entity_type="conversion_run",
        entity_id=response.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response


@router.post(
    "/dry-run",
    response_model=DryRunResponse,
    dependencies=[Depends(require(Permission.CONVERSION_PROCESS))],
)
def dry_run(
    db: DbSession, user: CurrentUserDep, payload: DryRunCreate
) -> DryRunResponse:
    """P3：试跑——用配置解析文件并计算预览，但不落库。供保存前即时验证。"""
    require_company_access(user, payload.company_id)
    upload_dir = Path(get_settings().upload_dir)
    return dry_run_conversion(db, payload, upload_dir)


@router.get(
    "",
    response_model=list[ConversionRunListItemResponse],
    dependencies=[Depends(require(Permission.READ))],
)
def list_runs(
    db: DbSession, user: CurrentUserDep, company_id: str | None = None
) -> list[ConversionRunListItemResponse]:
    """批次列表（不含预览行），按创建时间倒序。仅返回当前用户可访问公司的批次。"""
    return list_conversion_runs(db, company_id, accessible_company_filter(user))


@router.get(
    "/{run_id}",
    response_model=ConversionRunResponse,
    dependencies=[Depends(require(Permission.READ))],
)
def get_run(db: DbSession, user: CurrentUserDep, run_id: str) -> ConversionRunResponse:
    """批次详情（含预览行）。不存在则 404，存在但无权访问则 403。"""
    response = get_conversion_run(db, run_id)  # 不存在时抛 404
    require_company_access(user, response.company_id)  # 跨公司读取拦截
    return response


@router.get(
    "/{run_id}/preview-rows",
    response_model=Page[JournalPreviewRowData],
    dependencies=[Depends(require(Permission.READ))],
)
def list_run_preview_rows(
    db: DbSession,
    user: CurrentUserDep,
    run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[JournalPreviewRowData]:
    """分页返回某批次的日记账预览行，按 row_index 升序。不存在则 404，无权则 403。"""
    # 轻量加载父批次以取 company_id（存在性检查先于公司访问检查）
    run = db.get(ConversionRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion run not found: {run_id}",
        )
    require_company_access(user, run.company_id)
    return list_preview_rows(db, run_id, limit, offset)
