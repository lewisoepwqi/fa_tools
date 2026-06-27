"""P1-8: /api/bank-templates/detect 端点测试。

上传样本文件后，系统应自动识别：表头行、数据起始行、字段别名、金额模式、
日期格式（PRD §5.1.3 / §9.1）。
"""
from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.fixture()
def upload_dir(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield tmp_path / "uploads"
    get_settings.cache_clear()


FIXTURE = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"


def _upload(client) -> dict:
    return client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()


def test_detect_returns_auto_recognized_config(client, upload_dir) -> None:
    upload = _upload(client)

    response = client.post(
        "/api/bank-templates/detect",
        json={"source_file_id": upload["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    # 识别出表头行（fixture 第 0 行是表头）
    assert data["header_row_index"] == 0
    # 数据起始行紧跟表头
    assert data["data_start_row_index"] == 1
    assert data["file_type"] == "csv"
    # 字段别名应至少把"交易日期"映射到 transaction_date
    assert data["field_aliases"]["交易日期"] == "transaction_date"
    assert data["field_aliases"]["收入"] == "income_amount"
    assert data["field_aliases"]["支出"] == "expense_amount"
    # 金额模式推断为 income_expense_columns
    assert data["amount_mode"] == "income_expense_columns"
    # 日期格式候选
    assert "%Y-%m-%d" in data["date_formats"]


def test_detect_404_when_source_file_missing(client, upload_dir) -> None:
    response = client.post(
        "/api/bank-templates/detect",
        json={"source_file_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404
