"""转换时按文件选择工作表（per-file sheet）测试。

核心场景：流水文件的工作表名不是 "Sheet1"（如"明细"/"交易流水"），
旧实现因硬兜底 "Sheet1" 会报 Sheet not found。改造后：
1. 文件没有 Sheet1 也能转换（回退到文件首个工作表）
2. 用户可通过 source_files[].sheet_name 指定用哪个工作表
3. 多 sheet 文件选不同 sheet 会解析出不同数据
4. conversion_run_files 记录每文件实际用的 sheet 名（审计追溯）
"""

from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.core.config import get_settings


@pytest.fixture()
def upload_dir(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield tmp_path / "uploads"
    get_settings.cache_clear()


def _make_xlsx(path: Path, sheets: dict[str, list[list]]) -> None:
    """构造多工作表 xlsx。sheets = {sheet名: [行...]}。"""
    workbook = Workbook()
    first = True
    for name, rows in sheets.items():
        sheet = workbook.active if first else workbook.create_sheet()
        sheet.title = name
        for row in rows:
            sheet.append(row)
        first = False
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def _header_row():
    return [
        "交易日期", "入账日期", "收入", "支出", "余额",
        "对方户名", "对方账号", "摘要", "用途", "流水号",
    ]


def _upload_xlsx(client, upload_dir: Path, filename: str, path: Path) -> str:
    response = client.post(
        "/api/files/upload",
        files={
            "file": (
                filename,
                path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_bank_template(client, sheet_name: str | None = None) -> str:
    """建银行模板；sheet_selector_json 可控（测兜底逻辑）。"""
    version = {
        "file_type": "xlsx",
        "header_row_index": 0,
        "data_start_row_index": 1,
        "field_aliases_json": {
            "交易日期": "transaction_date",
            "入账日期": "posting_date",
            "收入": "income_amount",
            "支出": "expense_amount",
            "余额": "balance",
            "对方户名": "counterparty_name",
            "对方账号": "counterparty_account_no",
            "摘要": "summary",
            "用途": "purpose",
            "流水号": "bank_transaction_id",
        },
        "amount_mode": "income_expense_columns",
        "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
        "date_formats_json": ["%Y-%m-%d"],
        "created_by": "user-1",
    }
    if sheet_name is not None:
        version["sheet_selector_json"] = {"sheet_name": sheet_name}
    response = client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "xlsx模板",
            "bank_account_id": "bank-account-1",
            "version": version,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_journal_template(client) -> str:
    response = client.post(
        "/api/tools/bank-journal/journal-templates",
        json={
            "company_id": "company-1",
            "name": "标准日记账",
            "version": {
                "file_type": "xlsx",
                "columns_json": ["日期", "金额"],
                "required_columns_json": [],
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _run_from_config(client, company_id, source_file_ids, bank_id, journal_id, source_files=None):
    payload = {
        "company_id": company_id,
        "bank_account_id": "bank-account-1",
        "source_file_ids": source_file_ids,
        "bank_template_id": bank_id,
        "company_journal_template_id": journal_id,
    }
    if source_files is not None:
        payload["source_files"] = source_files
    return client.post("/api/tools/bank-journal/conversion-runs/from-config", json=payload)


def test_conversion_succeeds_when_file_has_no_sheet1(client, upload_dir) -> None:
    """文件工作表叫「明细」而非 Sheet1，模板也没配 sheet → 不再报错（回退首个 sheet）。"""
    xlsx_path = upload_dir / "no_sheet1.xlsx"
    _make_xlsx(xlsx_path, {
        "明细": [
            _header_row(),
            [date(2026, 6, 1), date(2026, 6, 1), "12000.00", "", "98000.00",
             "某客户", "6222", "货款", "6月费", "TXN001"],
        ]
    })
    file_id = _upload_xlsx(client, upload_dir, "no_sheet1.xlsx", xlsx_path)
    bank_id = _create_bank_template(client, sheet_name=None)  # 模板不配 sheet
    journal_id = _create_journal_template(client)

    response = _run_from_config(client, "company-1", [file_id], bank_id, journal_id)

    # 改造前会因 "Sheet not found: Sheet1" 报 500/400；改造后成功
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["summary"]["total_rows"] == 1
    assert data["summary"]["parse_failed_rows"] == 0


def test_conversion_uses_explicitly_selected_sheet(client, upload_dir) -> None:
    """多工作表文件：用户通过 source_files 选择用「交易流水」而非首个「汇总」。"""
    xlsx_path = upload_dir / "multi.xlsx"
    _make_xlsx(xlsx_path, {
        # 首个工作表「汇总」无有效流水数据
        "汇总": [["说明", "备注"], ["总计", "无明细"]],
        # 第二个工作表「交易流水」有真实流水
        "交易流水": [
            _header_row(),
            [date(2026, 6, 1), date(2026, 6, 1), "12000.00", "", "98000.00",
             "某客户", "6222", "货款", "6月费", "TXN001"],
            [date(2026, 6, 2), date(2026, 6, 2), "", "3000.00", "95000.00",
             "某供应商", "6223", "采购", "办公", "TXN002"],
        ],
    })
    file_id = _upload_xlsx(client, upload_dir, "multi.xlsx", xlsx_path)
    bank_id = _create_bank_template(client, sheet_name=None)
    journal_id = _create_journal_template(client)

    response = _run_from_config(
        client, "company-1", [file_id], bank_id, journal_id,
        source_files=[{"file_id": file_id, "sheet_name": "交易流水"}],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # 选了「交易流水」→ 解析出 2 行；若错选首个「汇总」会 0 行
    assert data["summary"]["total_rows"] == 2


def test_conversion_records_sheet_name_in_run_file(client_with_db, upload_dir, admin_auth) -> None:
    """conversion_run_files 记录每文件实际用的 sheet 名（审计追溯）。"""
    client, db = client_with_db
    # client_with_db 默认不带鉴权头，显式注入 admin
    client.headers.update(admin_auth)

    xlsx_path = upload_dir / "audit.xlsx"
    _make_xlsx(xlsx_path, {
        "交易流水": [
            _header_row(),
            [date(2026, 6, 1), date(2026, 6, 1), "12000.00", "", "98000.00",
             "某客户", "6222", "货款", "6月费", "TXN001"],
        ]
    })
    file_id = _upload_xlsx(client, upload_dir, "audit.xlsx", xlsx_path)
    bank_id = _create_bank_template(client, sheet_name=None)
    journal_id = _create_journal_template(client)

    response = _run_from_config(
        client, "company-1", [file_id], bank_id, journal_id,
        source_files=[{"file_id": file_id, "sheet_name": "交易流水"}],
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["id"]

    # 直接查库验证 conversion_run_files.source_sheet_name（同一 in-memory 引擎）
    from app.tools.bank_journal.models.conversion import ConversionRunFile
    rows = (
        db.query(ConversionRunFile)
        .filter(ConversionRunFile.conversion_run_id == run_id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].source_sheet_name == "交易流水"
