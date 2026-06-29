from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentUserDep, DbSession, require, require_company_access
from app.core.permissions import Permission
from app.models.file import SourceFile
from app.schemas.file import UploadedFileResponse
from app.services.audit_service import audit_ctx, record_audit_event
from app.services.file_service import save_uploaded_file

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post(
    "/upload",
    response_model=UploadedFileResponse,
    dependencies=[Depends(require(Permission.CONVERSION_PROCESS))],
)
async def upload_file(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    company_id: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008
) -> UploadedFileResponse:
    require_company_access(user, company_id)
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
        uploaded_by=user.id,
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

    response = UploadedFileResponse(company_id=company_id, uploaded_by=user.id, **saved)
    record_audit_event(
        db,
        company_id=company_id,
        actor_id=user.id,
        action="file.uploaded",
        entity_type="source_file",
        entity_id=source_file.id,
        after=response.model_dump(),
        **audit_ctx(request),
    )
    return response
