from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    company_id: str | None = None
    actor_id: str | None = None
    action: str
    entity_type: str
    entity_id: str
    before_json: dict[str, Any] | None = None
    after_json: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: str
