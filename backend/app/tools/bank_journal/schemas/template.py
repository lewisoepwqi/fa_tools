from typing import Any

from pydantic import BaseModel


class BankTemplateVersionCreate(BaseModel):
    file_type: str
    sheet_selector_json: dict[str, Any] | None = None
    header_row_index: int | None = None
    data_start_row_index: int | None = None
    field_aliases_json: dict[str, Any] | None = None
    date_formats_json: list[Any] | None = None
    amount_mode: str
    amount_config_json: dict[str, Any] | None = None
    unique_key_config_json: dict[str, Any] | None = None
    sample_file_id: str | None = None
    created_by: str | None = None


class BankTemplateVersionResponse(BankTemplateVersionCreate):
    version_no: int


class BankTemplateCreate(BaseModel):
    company_id: str | None = None
    name: str
    bank_name: str | None = None
    bank_account_id: str | None = None
    version: BankTemplateVersionCreate


class BankTemplateResponse(BaseModel):
    id: str
    company_id: str | None = None
    name: str
    bank_name: str | None = None
    bank_account_id: str | None = None
    status: str
    latest_version: BankTemplateVersionResponse


class BankTemplateDetectRequest(BaseModel):
    source_file_id: str
    sheet_name: str | None = None
    # 传入后，detect 会合并该公司的自定义扩展字段做表头识别
    company_id: str | None = None


class BankTemplateDetectResponse(BaseModel):
    file_type: str
    sheet_name: str
    header_row_index: int
    data_start_row_index: int
    field_aliases: dict[str, str]
    amount_mode: str
    amount_config: dict[str, str]
    date_formats: list[str]


class CompanyJournalTemplateVersionCreate(BaseModel):
    file_type: str
    sheet_name: str | None = None
    header_row_index: int | None = None
    data_start_row_index: int | None = None
    columns_json: list[Any] | None = None
    required_columns_json: list[Any] | None = None
    format_rules_json: dict[str, Any] | None = None
    sample_file_id: str | None = None
    created_by: str | None = None


class CompanyJournalTemplateVersionResponse(CompanyJournalTemplateVersionCreate):
    version_no: int


class CompanyJournalTemplateCreate(BaseModel):
    company_id: str
    name: str
    version: CompanyJournalTemplateVersionCreate


class CompanyJournalTemplateResponse(BaseModel):
    id: str
    company_id: str
    name: str
    status: str
    latest_version: CompanyJournalTemplateVersionResponse
