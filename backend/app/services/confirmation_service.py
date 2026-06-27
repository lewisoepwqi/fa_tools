from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import PreviewStatus
from app.models.conversion import Confirmation, JournalPreviewRow, ManualAdjustment


def record_manual_adjustment(
    db: Session,
    row_id: str,
    field_name: str,
    new_value: str,
    reason: str | None,
    adjusted_by: str,
) -> dict:
    row = db.query(JournalPreviewRow).filter(JournalPreviewRow.id == row_id).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview row not found: {row_id}",
        )
    output = dict(row.output_values_json or {})
    old_value = output.get(field_name)
    output[field_name] = new_value
    row.output_values_json = output
    row.updated_at = datetime.now(UTC)
    db.add(
        ManualAdjustment(
            id=str(uuid4()),
            journal_preview_row_id=row_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=new_value,
            reason=reason,
            adjusted_by=adjusted_by,
        )
    )
    db.commit()
    db.refresh(row)
    return {
        "row_id": row_id,
        "field_name": field_name,
        "new_value": new_value,
        "status": row.status,
    }


def confirm_preview_row(
    db: Session,
    row_id: str,
    confirmed_by: str,
    comment: str | None,
) -> dict:
    row = db.query(JournalPreviewRow).filter(JournalPreviewRow.id == row_id).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview row not found: {row_id}",
        )
    row.status = PreviewStatus.MANUALLY_CONFIRMED
    db.add(
        Confirmation(
            id=str(uuid4()),
            journal_preview_row_id=row_id,
            confirmation_type="manual",
            confirmed_by=confirmed_by,
            comment=comment,
        )
    )
    db.commit()
    db.refresh(row)
    return {"row_id": row_id, "status": row.status}
