from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.export import ExportCreate
from app.services.export_service import export_preview_rows_to_csv, export_preview_rows_to_xlsx

router = APIRouter(tags=["exports"])

_EXPORTS: dict[str, dict] = {}


@router.post("/api/conversion-runs/{run_id}/exports")
def create_export(run_id: str, payload: ExportCreate) -> dict:
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

    _EXPORTS[export_id] = {
        "export_id": export_id,
        "run_id": run_id,
        "file_type": payload.file_type,
        "storage_key": filename,
        "row_count": len(payload.rows),
        "exported_by": payload.exported_by,
        "only_confirmed": payload.only_confirmed,
    }

    return {
        "export_id": export_id,
        "file_type": payload.file_type,
        "row_count": len(payload.rows),
        "download_url": f"/api/exports/{export_id}/download",
    }


@router.get("/api/exports/{export_id}/download")
def download_export(export_id: str) -> FileResponse:
    export = _EXPORTS.get(export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    path = Path(get_settings().export_dir) / export["storage_key"]
    return FileResponse(
        path,
        filename=export["storage_key"],
        media_type="application/octet-stream",
    )
