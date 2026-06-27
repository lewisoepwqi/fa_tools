from pathlib import Path

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.config import get_settings
from app.schemas.conversion import ConversionRunCreate, ConversionRunResponse
from app.services.conversion_service import run_conversion

router = APIRouter(prefix="/api/conversion-runs", tags=["conversion-runs"])


@router.post("", response_model=ConversionRunResponse)
def start_conversion_run(
    db: DbSession, payload: ConversionRunCreate
) -> ConversionRunResponse:
    upload_dir = Path(get_settings().upload_dir)
    return run_conversion(db, payload, upload_dir)
