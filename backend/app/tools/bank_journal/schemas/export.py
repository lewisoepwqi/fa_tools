from typing import Any, Literal

from pydantic import BaseModel


class ExportCreate(BaseModel):
    file_type: Literal["csv", "xlsx"]
    columns: list[str]
    exported_by: str | None = None
    only_confirmed: bool = False
    # P0-5: 导出必填字段完整性校验（PRD §6.9.4）。缺失则不校验。
    required_columns: list[str] | None = None
    # 兼容历史用法：客户端可直接传入 rows（不查库，不走 only_confirmed 过滤）。
    # 新流程建议省略 rows，由后端按库内 preview rows 过滤导出。
    rows: list[dict[str, Any]] | None = None


class ExportReportSummary(BaseModel):
    """处理报告（PRD §6.9.7）。"""

    batch_id: str
    source_files: list[str]
    bank_template_version_id: str | None = None
    company_journal_template_version_id: str | None = None
    mapping_profile_version_id: str | None = None
    rule_version_ids: list[str]
    total_rows: int
    success_rows: int
    auto_confirmed_rows: int
    manually_confirmed_rows: int
    exception_rows: int
    exported_by: str | None = None
    exported_at: str
