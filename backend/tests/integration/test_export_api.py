"""导出端点测试（P0-3 only_confirmed 过滤 / P0-4 处理报告 / P0-5 必填校验）。"""

from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.fixture()
def upload_dir(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    get_settings.cache_clear()
    yield tmp_path / "exports"
    get_settings.cache_clear()


FIXTURE = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"


def _create_run(client) -> dict:
    upload = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()
    return client.post(
        "/api/tools/bank-journal/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [upload["id"]],
            "bank_parse_config": {
                "file_type": "csv",
                "sheet_name": "Sheet1",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases": {
                    "交易日期": "transaction_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "金额", "type": "field", "source": "net_amount"},
            ],
            "rules": [],
            "required_columns": ["日期"],
        },
    ).json()


def test_export_inline_rows_returns_download_metadata(client, upload_dir) -> None:
    """历史用法：客户端直接传入 rows（不查库）。"""
    created = _create_run(client)
    response = client.post(
        f"/api/tools/bank-journal/conversion-runs/{created['id']}/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "金额"],
            "rows": [{"日期": "2026-06-01", "金额": "12000.00"}],
            "exported_by": "user-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_type"] == "csv"
    assert payload["row_count"] == 1
    assert payload["download_url"].startswith("/api/tools/bank-journal/exports/")
    assert payload["report_url"].startswith("/api/tools/bank-journal/exports/")


def test_download_export_returns_file_contents(client, upload_dir) -> None:
    created = _create_run(client)
    create = client.post(
        f"/api/tools/bank-journal/conversion-runs/{created['id']}/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "金额"],
            "rows": [{"日期": "2026-06-01", "金额": "12000.00"}],
            "exported_by": "user-1",
        },
    ).json()
    download = client.get(create["download_url"])
    assert download.status_code == 200
    assert "日期" in download.text


def test_export_404_when_run_missing(client, upload_dir) -> None:
    response = client.post(
        "/api/tools/bank-journal/conversion-runs/00000000-0000-0000-0000-000000000000/exports",
        json={"file_type": "csv", "columns": ["日期"]},
    )
    assert response.status_code == 404


def test_export_from_db_rows_without_only_confirmed(client, upload_dir) -> None:
    """P0-3: 不传 rows、不设 only_confirmed → 导出全部 preview rows。"""
    created = _create_run(client)

    response = client.post(
        f"/api/tools/bank-journal/conversion-runs/{created['id']}/exports",
        json={"file_type": "csv", "columns": ["日期", "金额"], "exported_by": "user-1"},
    )

    assert response.status_code == 200
    assert response.json()["row_count"] == created["summary"]["total_rows"]


def test_export_only_confirmed_filters_needs_confirmation(client, upload_dir) -> None:
    """P0-3: only_confirmed=True → 仅导出已确认行（无规则命中时全部待确认 → 0 行）。"""
    created = _create_run(client)
    # 无规则命中，所有行都是 needs_confirmation

    response = client.post(
        f"/api/tools/bank-journal/conversion-runs/{created['id']}/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "金额"],
            "exported_by": "user-1",
            "only_confirmed": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["row_count"] == 0


def test_export_required_columns_validation_422(client, upload_dir) -> None:
    """P0-5: required_columns 中字段缺失 → 422。"""
    created = _create_run(client)
    response = client.post(
        f"/api/tools/bank-journal/conversion-runs/{created['id']}/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "金额"],
            "exported_by": "user-1",
            "required_columns": ["日期", "不存在的字段"],
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "不存在的字段" in detail["required_columns"]


def test_export_generates_processing_report(client, upload_dir) -> None:
    """P0-4: 导出同时生成处理报告，可下载，含 11 项字段。"""
    created = _create_run(client)
    export_response = client.post(
        f"/api/tools/bank-journal/conversion-runs/{created['id']}/exports",
        json={"file_type": "csv", "columns": ["日期", "金额"], "exported_by": "user-1"},
    ).json()

    report = client.get(export_response["report_url"])
    assert report.status_code == 200

    import json

    body = json.loads(report.text)
    assert body["batch_id"] == created["id"]
    assert body["total_rows"] == created["summary"]["total_rows"]
    # 报告 11 项字段齐备
    for field in (
        "batch_id",
        "source_files",
        "total_rows",
        "success_rows",
        "auto_confirmed_rows",
        "manually_confirmed_rows",
        "exception_rows",
        "exported_by",
        "exported_at",
    ):
        assert field in body


def test_export_report_404_when_missing(client, upload_dir) -> None:
    response = client.get("/api/tools/bank-journal/exports/no-such-export/report")
    assert response.status_code == 404
