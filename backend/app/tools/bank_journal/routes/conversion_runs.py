from pathlib import Path

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.config import get_settings
from app.services.audit_service import record_audit_event
from app.tools.bank_journal.schemas.conversion import (
    ConversionRunCreate,
    ConversionRunListItemResponse,
    ConversionRunResponse,
)
from app.tools.bank_journal.services.conversion_service import (
    get_conversion_run,
    list_conversion_runs,
    run_conversion,
)

router = APIRouter(
    prefix="/api/tools/bank-journal/conversion-runs", tags=["conversion-runs"]
)


@router.post("", response_model=ConversionRunResponse)
def start_conversion_run(
    db: DbSession, payload: ConversionRunCreate
) -> ConversionRunResponse:
    upload_dir = Path(get_settings().upload_dir)
    response = run_conversion(db, payload, upload_dir)
    record_audit_event(
        db,
        company_id=payload.company_id,
        actor_id=None,
        action="conversion_run.created",
        entity_type="conversion_run",
        entity_id=response.id,
        after=response.model_dump(),
    )
    return response


@router.get("", response_model=list[ConversionRunListItemResponse])
def list_runs(
    db: DbSession, company_id: str | None = None
) -> list[ConversionRunListItemResponse]:
    """批次列表（不含预览行），按创建时间倒序。"""
    return list_conversion_runs(db, company_id)


@router.get("/{run_id}", response_model=ConversionRunResponse)
def get_run(db: DbSession, run_id: str) -> ConversionRunResponse:
    """批次详情（含预览行）。不存在则 404。"""
    return get_conversion_run(db, run_id)
