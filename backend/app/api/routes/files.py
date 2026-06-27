from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import DbSession
from app.models.file import SourceFile
from app.schemas.file import UploadedFileResponse
from app.services.file_service import save_uploaded_file

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse)
async def upload_file(
    db: DbSession,
    company_id: str = Form(...),
    uploaded_by: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008
) -> UploadedFileResponse:
    content = await file.read()
    try:
        saved = save_uploaded_file(file.filename or "upload", content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc

    source_file = SourceFile(
        id=saved["id"],
        company_id=company_id,
        uploaded_by=uploaded_by,
        original_filename=saved["original_filename"],
        file_type=saved["file_type"],
        file_size=saved["file_size"],
        sha256=saved["sha256"],
        storage_key=saved["storage_key"],
        status=saved["status"],
    )
    db.add(source_file)
    db.commit()
    db.refresh(source_file)

    return UploadedFileResponse(company_id=company_id, uploaded_by=uploaded_by, **saved)
