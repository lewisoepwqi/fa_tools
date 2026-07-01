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
    # 展示名（联表解析，供前端直接显示，避免裸 ID）
    created_by_name: str | None = None
    sample_file_name: str | None = None


class BankTemplateCreate(BaseModel):
    company_id: str | None = None
    name: str
    bank_name: str | None = None
    bank_account_id: str | None = None
    version: BankTemplateVersionCreate


class BankTemplateResponse(BaseModel):
    id: str
    company_id: str | None = None
    company_name: str | None = None
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


class SourceFileSheetsResponse(BaseModel):
    """已上传文件的工作表列表（供「上传后选 sheet」能力使用）。

    CSV / XLS 等无工作表概念的文件返回空列表，前端据此隐藏选择器。
    """

    file_id: str
    sheets: list[str]


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
    # 展示名（联表解析，供前端直接显示，避免裸 ID）
    created_by_name: str | None = None
    sample_file_name: str | None = None


class CompanyJournalTemplateCreate(BaseModel):
    company_id: str
    name: str
    version: CompanyJournalTemplateVersionCreate


class CompanyJournalTemplateResponse(BaseModel):
    id: str
    company_id: str
    company_name: str | None = None
    name: str
    status: str
    latest_version: CompanyJournalTemplateVersionResponse


class JournalTemplateDetectRequest(BaseModel):
    source_file_id: str
    sheet_name: str | None = None


class JournalTemplateDetectResponse(BaseModel):
    """从日记账样本识别出的模板配置（表头行 + 列名）。"""

    file_type: str
    sheet_name: str
    header_row_index: int
    data_start_row_index: int
    columns: list[str]
    required_columns: list[str]
