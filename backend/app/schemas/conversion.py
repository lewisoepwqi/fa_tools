from typing import Any

from pydantic import BaseModel

from app.core.enums import ExceptionCode, PreviewStatus


class JournalPreviewRowData(BaseModel):
    id: str | None = None
    row_index: int
    output_values: dict[str, Any]
    status: PreviewStatus
    exception_codes: list[ExceptionCode]
    matched_rule_version_ids: list[str]
    rule_trace: list[dict[str, Any]]


class BankParseConfig(BaseModel):
    file_type: str
    sheet_name: str
    header_row_index: int
    data_start_row_index: int
    field_aliases: dict[str, str]
    amount_mode: str
    amount_config: dict[str, str]
    date_formats: list[str]


class ConversionRunCreate(BaseModel):
    company_id: str
    bank_account_id: str
    source_file_ids: list[str]
    bank_parse_config: BankParseConfig
    mappings: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    required_columns: list[str]


class ConversionRunSummary(BaseModel):
    total_rows: int


class ConversionRunResponse(BaseModel):
    id: str
    status: str
    summary: ConversionRunSummary
    preview_rows: list[JournalPreviewRowData]
