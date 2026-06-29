from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    require,
    require_company_access,
)
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event
from app.tools.bank_journal.models.conversion import ConversionRun, JournalPreviewRow
from app.tools.bank_journal.schemas.confirmation import (
    ConfirmationRequest,
    ManualAdjustmentRequest,
)
from app.tools.bank_journal.services.confirmation_service import (
    confirm_preview_row,
    record_manual_adjustment,
)

router = APIRouter(
    prefix="/api/tools/bank-journal/preview-rows", tags=["preview-rows"]
)


@router.patch(
    "/{row_id}",
    response_model=dict[str, Any],
    dependencies=[Depends(require(Permission.CONVERSION_PROCESS))],
)
def adjust_preview_row(
    row_id: str,
    payload: ManualAdjustmentRequest,
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
) -> dict[str, Any]:
    _require_row_company_access(db, user, row_id)
    payload.adjusted_by = user.id
    result = record_manual_adjustment(
        db,
        row_id,
        payload.field_name,
        payload.new_value,
        payload.reason,
        payload.adjusted_by,
    )
    record_audit_event(
        db,
        company_id=None,
        actor_id=user.id,
        action="preview_row.adjusted",
        entity_type="journal_preview_row",
        entity_id=row_id,
        after=result,
        **audit_ctx(request),
    )
    return result


def _require_row_company_access(db: DbSession, user: CurrentUserDep, row_id: str) -> None:
    """加载预览行 → 所属批次 → 按批次公司做写访问校验。

    区分两种 None：
    - row 本身不存在 → return，交由 service 层保持原有 404 语义（避免 404→403）。
    - row 存在但 run 已消失（孤儿）→ 无法确认归属，fail-closed：抛 403 而非放行。
    """
    row = db.query(JournalPreviewRow).filter(JournalPreviewRow.id == row_id).first()
    if row is None:
        # 行不存在：交由 service 层抛 404，此处不干预
        return
    run = db.query(ConversionRun).filter(ConversionRun.id == row.conversion_run_id).first()
    if run is None:
        # 孤儿行：父批次已丢失，无法校验归属，拒绝访问
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法确认预览行所属公司，拒绝访问",
        )
    require_company_access(user, run.company_id)


@router.post(
    "/{row_id}/confirm",
    response_model=dict[str, Any],
    dependencies=[Depends(require(Permission.CONVERSION_CONFIRM))],
)
def confirm_preview_row_route(
    row_id: str,
    payload: ConfirmationRequest,
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
) -> dict[str, Any]:
    _require_row_company_access(db, user, row_id)
    payload.confirmed_by = user.id
    result = confirm_preview_row(db, row_id, payload.confirmed_by, payload.comment)
    record_audit_event(
        db,
        company_id=None,
        actor_id=user.id,
        action="preview_row.confirmed",
        entity_type="journal_preview_row",
        entity_id=row_id,
        after=result,
        **audit_ctx(request),
    )
    return result
