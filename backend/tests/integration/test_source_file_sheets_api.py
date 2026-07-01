"""列出已上传文件的工作表（sheets）端点测试。

`GET /api/tools/bank-journal/bank-templates/source-files/{file_id}/sheets`
供「上传后让用户选择工作表」能力使用——每个文件的 sheet 名不同，
转换前需让用户看到该文件有哪些 sheet 可选。
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


CSV_FIXTURE = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"


def _upload_xlsx(client, upload_dir: Path, filename: str, sheet_names: list[str]) -> str:
    """构造含多个工作表的 xlsx 并上传，返回 file_id。"""
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_xlsx = upload_dir / f"_tmp_{filename}"
    workbook = Workbook()
    workbook.active.title = sheet_names[0]
    for extra in sheet_names[1:]:
        workbook.create_sheet(extra)
    # 给每个 sheet 写一行表头，确保非空
    header = [
        "交易日期", "入账日期", "收入", "支出", "余额",
        "对方户名", "对方账号", "摘要", "用途", "流水号",
    ]
    workbook.active.append(header)
    workbook.active.append(
        [
            date(2026, 6, 1), date(2026, 6, 1), "12000.00", "",
            "98000.00", "某客户", "6222", "货款", "6月费", "TXN001",
        ]
    )
    workbook.save(tmp_xlsx)
    response = client.post(
        "/api/files/upload",
        files={
            "file": (
                filename,
                tmp_xlsx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert response.status_code == 200, response.text
    tmp_xlsx.unlink(missing_ok=True)
    return response.json()["id"]


def _upload_csv(client) -> str:
    response = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", CSV_FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_list_sheets_returns_all_sheet_names(client, upload_dir) -> None:
    """xlsx 文件返回全部工作表名（按文件内顺序）。"""
    file_id = _upload_xlsx(client, upload_dir, "multi.xlsx", ["明细", "交易流水", "汇总"])

    response = client.get(f"/api/tools/bank-journal/bank-templates/source-files/{file_id}/sheets")

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == file_id
    assert data["sheets"] == ["明细", "交易流水", "汇总"]


def test_list_sheets_for_csv_returns_empty(client) -> None:
    """CSV 无工作表概念，返回空列表（前端据此隐藏选择器）。"""
    file_id = _upload_csv(client)

    response = client.get(f"/api/tools/bank-journal/bank-templates/source-files/{file_id}/sheets")

    assert response.status_code == 200
    assert response.json()["sheets"] == []


def test_list_sheets_404_when_file_missing(client) -> None:
    """源文件不存在 → 404。"""
    response = client.get(
        "/api/tools/bank-journal/bank-templates/source-files/00000000-0000-0000-0000-000000000000/sheets"
    )
    assert response.status_code == 404
