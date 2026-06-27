from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.conversion import Export
from app.schemas.export import ExportCreate
from app.services.audit_service import record_audit_event
from app.services.export_service import (
    export_preview_rows_to_csv,
    export_preview_rows_to_xlsx,
)

router = APIRouter(tags=["exports"])


@router.post("/api/conversion-runs/{run_id}/exports")
def create_export(run_id: str, payload: ExportCreate, db: DbSession) -> dict:
    export_id = str(uuid4())
    output_dir = Path(get_settings().export_dir)

    if payload.file_type == "xlsx":
        filename = f"{export_id}.xlsx"
        export_preview_rows_to_xlsx(
            rows=payload.rows,
            columns=payload.columns,
            output_dir=output_dir,
            filename=filename,
        )
    else:
        filename = f"{export_id}.csv"
        export_preview_rows_to_csv(
            rows=payload.rows,
            columns=payload.columns,
            output_dir=output_dir,
            filename=filename,
        )

    export = Export(
        id=export_id,
        conversion_run_id=run_id,
        exported_by=payload.exported_by,
        file_type=payload.file_type,
        storage_key=filename,
        row_count=len(payload.rows),
        only_confirmed=payload.only_confirmed,
    )
    db.add(export)
    db.commit()

    response = {
        "export_id": export_id,
        "file_type": payload.file_type,
        "row_count": len(payload.rows),
        "download_url": f"/api/exports/{export_id}/download",
    }
    record_audit_event(
        db,
        company_id=None,
        actor_id=payload.exported_by,
        action="export.created",
        entity_type="export",
        entity_id=export_id,
        after=response,
    )
    return response


@router.get("/api/exports/{export_id}/download")
def download_export(export_id: str, db: DbSession) -> FileResponse:
    export = db.query(Export).filter(Export.id == export_id).first()
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    path = Path(get_settings().export_dir) / export.storage_key
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found"
        )
    return FileResponse(
        path,
        filename=export.storage_key,
        media_type="application/octet-stream",
    )
