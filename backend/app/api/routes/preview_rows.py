from typing import Any

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.confirmation import ConfirmationRequest, ManualAdjustmentRequest
from app.services.audit_service import record_audit_event
from app.services.confirmation_service import confirm_preview_row, record_manual_adjustment

router = APIRouter(prefix="/api/preview-rows", tags=["preview-rows"])


@router.patch("/{row_id}", response_model=dict[str, Any])
def adjust_preview_row(
    row_id: str, payload: ManualAdjustmentRequest, db: DbSession
) -> dict[str, Any]:
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
        actor_id=payload.adjusted_by,
        action="preview_row.adjusted",
        entity_type="journal_preview_row",
        entity_id=row_id,
        after=result,
    )
    return result


@router.post("/{row_id}/confirm", response_model=dict[str, Any])
def confirm_preview_row_route(
    row_id: str, payload: ConfirmationRequest, db: DbSession
) -> dict[str, Any]:
    result = confirm_preview_row(db, row_id, payload.confirmed_by, payload.comment)
    record_audit_event(
        db,
        company_id=None,
        actor_id=payload.confirmed_by,
        action="preview_row.confirmed",
        entity_type="journal_preview_row",
        entity_id=row_id,
        after=result,
    )
    return result
