import pytest
from pathlib import Path

from app.core.config import get_settings


@pytest.fixture()
def upload_dir(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield tmp_path / "uploads"
    get_settings.cache_clear()


def test_upload_csv_file_returns_file_metadata(client, upload_dir) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"
    response = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", fixture.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_filename"] == "bank_statement_basic.csv"
    assert payload["file_type"] == "csv"
    assert len(payload["sha256"]) == 64

    stored_file = upload_dir / payload["storage_key"]
    assert stored_file.exists()


def test_upload_unsupported_file_type_returns_client_error(client, upload_dir) -> None:
    before = set(upload_dir.iterdir()) if upload_dir.exists() else set()

    response = client.post(
        "/api/files/upload",
        files={"file": ("note.txt", b"hello", "text/plain")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )

    assert response.status_code == 415
    body = response.json()
    detail = body["detail"]
    assert "Unsupported file type" in detail
    assert "txt" in detail

    after = set(upload_dir.iterdir()) if upload_dir.exists() else set()
    assert before == after


def test_create_bank_template_version(client) -> None:
    response = client.post(
        "/api/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中国银行 CSV",
            "bank_name": "中国银行",
            "bank_account_id": "bank-account-1",
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"mode": "first"},
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {"交易日期": "transaction_date"},
                "date_formats_json": ["%Y-%m-%d"],
                "amount_mode": "income_expense_columns",
                "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
                "unique_key_config_json": {"fields": ["流水号"]},
                "sample_file_id": "file-1",
                "created_by": "user-1",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "中国银行 CSV"
    assert payload["latest_version"]["version_no"] == 1
