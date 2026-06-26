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
