from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.file import UploadedFileResponse
from app.services.file_service import save_uploaded_file

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse)
async def upload_file(
    company_id: str = Form(...),
    uploaded_by: str = Form(...),
    file: UploadFile = File(...),
) -> UploadedFileResponse:
    content = await file.read()
    try:
        saved = save_uploaded_file(file.filename or "upload", content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc

    return UploadedFileResponse(company_id=company_id, uploaded_by=uploaded_by, **saved)
