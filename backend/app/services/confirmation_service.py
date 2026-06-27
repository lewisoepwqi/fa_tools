from __future__ import annotations

from app.core.enums import PreviewStatus

PREVIEW_ROW_STORE: dict[str, dict] = {}


def record_manual_adjustment(
    row_id: str,
    field_name: str,
    new_value: str,
    reason: str | None,
    adjusted_by: str,
) -> dict:
    row = PREVIEW_ROW_STORE.setdefault(
        row_id,
        {
            "row_id": row_id,
            "output_values": {},
            "adjustments": [],
            "status": PreviewStatus.NEEDS_CONFIRMATION,
        },
    )
    row["output_values"][field_name] = new_value
    row["adjustments"].append(
        {
            "field_name": field_name,
            "new_value": new_value,
            "reason": reason,
            "adjusted_by": adjusted_by,
        }
    )
    return {
        "row_id": row_id,
        "field_name": field_name,
        "new_value": new_value,
        "status": row["status"],
    }


def confirm_preview_row(
    row_id: str,
    confirmed_by: str,
    comment: str | None,
) -> dict:
    row = PREVIEW_ROW_STORE.setdefault(
        row_id,
        {
            "row_id": row_id,
            "output_values": {},
            "adjustments": [],
            "status": PreviewStatus.NEEDS_CONFIRMATION,
        },
    )
    row["status"] = PreviewStatus.MANUALLY_CONFIRMED
    row["confirmation"] = {"confirmed_by": confirmed_by, "comment": comment}
    return {"row_id": row_id, "status": row["status"]}
