from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import CurrentUserDep, DbSession, require
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event
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
