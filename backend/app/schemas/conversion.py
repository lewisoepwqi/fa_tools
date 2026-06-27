from typing import Any

from pydantic import BaseModel

from app.core.enums import ExceptionCode, PreviewStatus


class JournalPreviewRowData(BaseModel):
    row_index: int
    output_values: dict[str, Any]
    status: PreviewStatus
    exception_codes: list[ExceptionCode]
    matched_rule_version_ids: list[str]
    rule_trace: list[dict[str, Any]]
