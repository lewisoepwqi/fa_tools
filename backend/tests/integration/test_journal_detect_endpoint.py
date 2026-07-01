"""日记账模板 detect 端点测试。

`POST /api/tools/bank-journal/journal-templates/detect`
从已上传的日记账样本文件自动识别表头行与列名，对齐银行模板 detect 体验。
"""


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


def _upload_csv(client, content: bytes, filename: str = "journal_sample.csv") -> str:
    response = client.post(
        "/api/files/upload",
        files={"file": (filename, content, "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_detect_returns_columns_from_csv(client, upload_dir) -> None:
    """从日记账样本 CSV 识别出表头行与列名。"""
    csv_bytes = (
        "凭证号,日期,摘要,科目,借方,贷方,余额\n"
        "记-001,2026-07-01,收客户货款,银行存款,12000,,12000\n"
    ).encode()
    file_id = _upload_csv(client, csv_bytes)

    response = client.post(
        "/api/tools/bank-journal/journal-templates/detect",
        json={"source_file_id": file_id},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["header_row_index"] == 0
    assert data["data_start_row_index"] == 1
    assert data["columns"] == ["凭证号", "日期", "摘要", "科目", "借方", "贷方", "余额"]
    assert "日期" in data["required_columns"]
    assert "科目" in data["required_columns"]


def test_detect_skips_title_row(client, upload_dir) -> None:
    """首行是公司标题，表头应在第 1 行。"""
    csv_bytes = (
        "某某公司日记账\n"
        "日期,摘要,科目,金额\n"
        "2026-07-01,货款,银行存款,12000\n"
    ).encode()
    file_id = _upload_csv(client, csv_bytes)

    response = client.post(
        "/api/tools/bank-journal/journal-templates/detect",
        json={"source_file_id": file_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["header_row_index"] == 1
    assert data["columns"] == ["日期", "摘要", "科目", "金额"]


def test_detect_from_xlsx(client, upload_dir) -> None:
    """从 xlsx 样本识别（含工作表名）。"""
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_xlsx = upload_dir / "_tmp_journal.xlsx"
    workbook = Workbook()
    workbook.active.title = "日记账"
    workbook.active.append(["日期", "摘要", "科目", "金额"])
    workbook.active.append(["2026-07-01", "货款", "银行存款", "12000"])
    workbook.save(tmp_xlsx)
    upload_resp = client.post(
        "/api/files/upload",
        files={
            "file": (
                "journal.xlsx",
                tmp_xlsx.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]
    tmp_xlsx.unlink(missing_ok=True)

    response = client.post(
        "/api/tools/bank-journal/journal-templates/detect",
        json={"source_file_id": file_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_type"] == "xlsx"
    assert data["sheet_name"] == "日记账"
    assert data["columns"] == ["日期", "摘要", "科目", "金额"]


def test_detect_404_when_source_file_missing(client, upload_dir) -> None:
    """源文件不存在 → 404。"""
    response = client.post(
        "/api/tools/bank-journal/journal-templates/detect",
        json={"source_file_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_detect_403_when_user_lacks_company_access(
    client_with_db, upload_dir, make_user, auth_headers
) -> None:
    """跨公司读取拦截：仅授权 company-2 的 template_admin 不能 detect company-1 的文件。

    detect 端点会读取源文件元数据并解析文件内容，必须与 list_source_file_sheets
    一样做 require_company_access 校验，否则构成跨租户信息泄露。
    """
    client, db = client_with_db
    # client_with_db 默认不带鉴权头：上传用 admin（建文件归 admin），detect 才是被测越权点
    admin_headers = auth_headers(make_user(db, roles=["admin"]))
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_csv = upload_dir / "_tmp_journal_co1.csv"
    tmp_csv.write_text("日期,摘要,科目,金额\n2026-07-01,货款,银行存款,12000\n", encoding="utf-8")
    upload_resp = client.post(
        "/api/files/upload",
        files={"file": ("journal_co1.csv", tmp_csv.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
        headers=admin_headers,
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]
    tmp_csv.unlink(missing_ok=True)

    # 仅授权 company-2 的 template_admin（有 TEMPLATE_MANAGE，但非跨公司角色）
    other = make_user(db, roles=["template_admin"], company_ids=["company-2"])

    response = client.post(
        "/api/tools/bank-journal/journal-templates/detect",
        json={"source_file_id": file_id},
        headers=auth_headers(other),
    )
    assert response.status_code == 403
