from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.tools.bank_journal.enums import ExceptionCode, PreviewStatus


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
    # P0-2: 可选快照本次转换使用的版本化配置 ID（PRD §10.3.3 任意导出文件可
    # 查看使用的模板/映射/规则版本）。缺失则留空（兼容历史内联配置用法）。
    bank_template_version_id: str | None = None
    company_journal_template_version_id: str | None = None
    mapping_profile_version_id: str | None = None


class ConversionRunFromConfigCreate(BaseModel):
    """P0：用已配置的版本化模板/映射/规则驱动转换。

    与 ``ConversionRunCreate``（内联传 parse_config/mappings/rules）相对，
    本 schema 只传配置 ID，服务端从 DB 查最新版本并拼装内联参数后执行同一套
    parse/preview 逻辑。让用户在四个配置模块里的配置真正生效。

    每类配置支持「指定版本 ID」或「指定父 ID（自动取最新版本）」二选一。
    """

    company_id: str
    bank_account_id: str
    source_file_ids: list[str]
    bank_template_version_id: str | None = None
    bank_template_id: str | None = None
    company_journal_template_version_id: str | None = None
    company_journal_template_id: str | None = None
    mapping_profile_version_id: str | None = None
    mapping_profile_id: str | None = None
    rule_ids: list[str] = []
    required_columns: list[str] = []


class DryRunCreate(ConversionRunFromConfigCreate):
    """P3：试跑请求。复用 from-config 的配置选择，额外限制返回行数。"""

    limit: int = 20


class DryRunResponse(BaseModel):
    """P3：试跑结果（不落库）。只返回前 N 行预览 + 统计，供配置时即时验证。"""

    summary: "ConversionRunSummary"
    preview_rows: list[JournalPreviewRowData]


class ConversionRunSummary(BaseModel):
    total_rows: int = 0
    parse_failed_rows: int = 0


class ConversionRunListItemResponse(BaseModel):
    """批次列表项（不含预览行，避免大响应）。"""

    id: str
    company_id: str
    bank_account_id: str | None = None
    status: str
    summary: ConversionRunSummary
    created_at: datetime | None = None
    completed_at: datetime | None = None
    bank_template_version_id: str | None = None
    company_journal_template_version_id: str | None = None
    mapping_profile_version_id: str | None = None


class ConversionRunResponse(BaseModel):
    id: str
    status: str
    summary: ConversionRunSummary
    preview_rows: list[JournalPreviewRowData]
    company_id: str | None = None
    bank_account_id: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    bank_template_version_id: str | None = None
    company_journal_template_version_id: str | None = None
    mapping_profile_version_id: str | None = None
