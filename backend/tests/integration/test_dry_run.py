"""P3：试跑端点（不落库）测试。

验证 dry-run 用配置解析文件并返回前 N 行预览，但不创建 ConversionRun / 事务行。
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


def _upload_csv(client) -> str:
    response = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_bank_template(client) -> str:
    response = client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中行CSV",
            "bank_account_id": "bank-account-1",
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"sheet_name": "Sheet1"},
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {
                    "交易日期": "transaction_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                    "余额": "balance",
                    "摘要": "summary",
                    "流水号": "bank_transaction_id",
                },
                "amount_mode": "income_expense_columns",
                "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats_json": ["%Y-%m-%d"],
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_dry_run_returns_preview_without_persisting(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)

    runs_before = client.get("/api/tools/bank-journal/conversion-runs").json()
    response = client.post(
        "/api/tools/bank-journal/conversion-runs/dry-run",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    # 返回了预览行
    assert data["summary"]["total_rows"] >= 1
    assert "preview_rows" in data

    # 关键：试跑不落库——批次列表不应增长
    runs_after = client.get("/api/tools/bank-journal/conversion-runs").json()
    assert len(runs_after) == len(runs_before)


def test_dry_run_respects_limit(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)

    response = client.post(
        "/api/tools/bank-journal/conversion-runs/dry-run",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
            "limit": 1,
        },
    )
    assert response.status_code == 200
    assert len(response.json()["preview_rows"]) <= 1
