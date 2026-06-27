from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=list[Any])
def list_audit_logs() -> list[Any]:
    return []
