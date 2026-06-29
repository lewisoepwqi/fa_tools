from pathlib import Path

import pytest

from app.core.config import get_settings
from app.tools.bank_journal.models.conversion import BankTransaction


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
        "/api/tools/bank-journal/bank-templates",
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


def test_start_conversion_run_creates_preview_rows(client) -> None:
    upload = client.post(
        "/api/files/upload",
        files={
            "file": (
                "bank_statement_basic.csv",
                (Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv").read_bytes(),
                "text/csv",
            )
        },
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    response = client.post(
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
                    "入账日期": "posting_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                    "余额": "balance",
                    "对方户名": "counterparty_name",
                    "对方账号": "counterparty_account_no",
                    "摘要": "summary",
                    "用途": "purpose",
                    "流水号": "bank_transaction_id"
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"]
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "摘要", "type": "rule_output", "source": "journal_summary"},
                {"target": "科目", "type": "rule_output", "source": "account_subject"},
                {"target": "金额", "type": "field", "source": "net_amount"}
            ],
            "rules": [
                {
                    "id": "rule-1",
                    "version_id": "rule-version-1",
                    "priority": 10,
                    "conditions": {
                        "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                    },
                    "actions": [
                        {"field": "journal_summary", "value": "收到客户款项"},
                        {"field": "account_subject", "value": "银行存款"}
                    ],
                    "allow_auto_confirm": False
                }
            ],
            "required_columns": ["日期", "摘要", "科目", "金额"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_rows"] == 2
    assert payload["preview_rows"][0]["output_values"]["科目"] == "银行存款"
    assert payload["preview_rows"][1]["status"] == "needs_confirmation"


def test_confirm_preview_row_after_manual_adjustment(client) -> None:
    upload = client.post(
        "/api/files/upload",
        files={
            "file": (
                "bank_statement_basic.csv",
                (Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv").read_bytes(),
                "text/csv",
            )
        },
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    run = client.post(
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
                    "入账日期": "posting_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                    "余额": "balance",
                    "对方户名": "counterparty_name",
                    "对方账号": "counterparty_account_no",
                    "摘要": "summary",
                    "用途": "purpose",
                    "流水号": "bank_transaction_id"
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"]
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "摘要", "type": "rule_output", "source": "journal_summary"},
                {"target": "科目", "type": "rule_output", "source": "account_subject"},
                {"target": "金额", "type": "field", "source": "net_amount"}
            ],
            "rules": [
                {
                    "id": "rule-1",
                    "version_id": "rule-version-1",
                    "priority": 10,
                    "conditions": {
                        "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                    },
                    "actions": [
                        {"field": "journal_summary", "value": "收到客户款项"},
                        {"field": "account_subject", "value": "银行存款"}
                    ],
                    "allow_auto_confirm": False
                }
            ],
            "required_columns": ["日期", "摘要", "科目", "金额"],
        },
    ).json()

    row_id = run["preview_rows"][1]["id"]

    patch_response = client.patch(
        f"/api/tools/bank-journal/preview-rows/{row_id}",
        json={
            "field_name": "科目",
            "new_value": "银行存款",
            "reason": "人工确认供应商付款科目",
            "adjusted_by": "user-1",
        },
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["field_name"] == "科目"

    confirm_response = client.post(
        f"/api/tools/bank-journal/preview-rows/{row_id}/confirm",
        json={"confirmed_by": "user-1", "comment": "已核对"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "manually_confirmed"


def test_list_bank_templates_returns_persisted_template(client) -> None:
    create = client.post(
        "/api/tools/bank-journal/bank-templates",
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
    ).json()
    listed = client.get("/api/tools/bank-journal/bank-templates").json()
    assert any(t["id"] == create["id"] for t in listed)
    assert listed[0]["latest_version"]["version_no"] == 1


def test_creating_a_bank_template_records_an_audit_event(client) -> None:
    client.post(
        "/api/tools/bank-journal/bank-templates",
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
    logs = client.get("/api/audit-logs").json()
    assert any(log["action"] == "bank_template.created" for log in logs)


def test_full_conversion_flow_end_to_end(client) -> None:
    # 1. Upload a real CSV → source file persisted
    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"
    upload = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", fixture.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["id"]

    # 2. Convert → conversion run + bank_transactions + journal_preview_rows persisted
    run = client.post(
        "/api/tools/bank-journal/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [upload_id],
            "bank_parse_config": {
                "file_type": "csv", "sheet_name": "Sheet1",
                "header_row_index": 0, "data_start_row_index": 1,
                "field_aliases": {
                    "交易日期": "transaction_date", "入账日期": "posting_date",
                    "收入": "income_amount", "支出": "expense_amount", "余额": "balance",
                    "对方户名": "counterparty_name", "对方账号": "counterparty_account_no",
                    "摘要": "summary", "用途": "purpose", "流水号": "bank_transaction_id",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "摘要", "type": "rule_output", "source": "journal_summary"},
                {"target": "科目", "type": "rule_output", "source": "account_subject"},
                {"target": "金额", "type": "field", "source": "net_amount"},
            ],
            "rules": [
                {"id": "rule-1", "version_id": "rule-version-1", "priority": 10,
                 "conditions": {"all": [{"field": "summary", "op": "contains", "value": "货款"}]},
                 "actions": [
                     {"field": "journal_summary", "value": "收到客户款项"},
                     {"field": "account_subject", "value": "银行存款"},
                 ],
                 "allow_auto_confirm": False},
            ],
            "required_columns": ["日期", "摘要", "科目", "金额"],
        },
    )
    assert run.status_code == 200
    run_payload = run.json()
    assert run_payload["summary"]["total_rows"] == 2
    # 2nd row is the expense row (采购款) → needs_confirmation; take its persisted id
    row_id = run_payload["preview_rows"][1]["id"]
    assert row_id is not None

    # 3. Manual adjustment → ManualAdjustment persisted, output_values updated
    patch = client.patch(
        f"/api/tools/bank-journal/preview-rows/{row_id}",
        json={"field_name": "科目", "new_value": "管理费用",
              "reason": "人工指定采购科目", "adjusted_by": "user-1"},
    )
    assert patch.status_code == 200
    assert patch.json()["field_name"] == "科目"

    # 4. Confirm → Confirmation persisted, status → manually_confirmed
    confirm = client.post(
        f"/api/tools/bank-journal/preview-rows/{row_id}/confirm",
        json={"confirmed_by": "user-1", "comment": "已核对"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "manually_confirmed"

    # 5. Export → Export persisted, file written
    export = client.post(
        f"/api/tools/bank-journal/conversion-runs/{run_payload['id']}/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "摘要", "科目", "金额"],
            "rows": [r["output_values"] for r in run_payload["preview_rows"]],
            "exported_by": "user-1",
            "only_confirmed": False,
        },
    )
    assert export.status_code == 200
    download_url = export.json()["download_url"]
    assert download_url.startswith("/api/tools/bank-journal/exports/")

    # 6. Download → FileResponse with CSV content
    download = client.get(download_url)
    assert download.status_code == 200
    assert "日期" in download.content.decode("utf-8-sig")

    # 7. Audit trail captured the full chain
    logs = client.get("/api/audit-logs").json()
    actions = {log["action"] for log in logs}
    for expected in {
        "file.uploaded", "conversion_run.created",
        "preview_row.adjusted", "preview_row.confirmed", "export.created",
    }:
        assert expected in actions, f"missing audit action: {expected}"


def test_bad_mapping_isolated_per_row(client, upload_dir) -> None:
    """单行映射错误不应中断整批——坏映射让每行降级到 parse_failed，整批返回 200。"""
    upload = client.post(
        "/api/files/upload",
        files={
            "file": (
                "bank_statement_basic.csv",
                (Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv").read_bytes(),
                "text/csv",
            )
        },
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    response = client.post(
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
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [
                {"target": "科目", "type": "field", "source": "不存在字段"},
            ],
            "rules": [],
            "required_columns": ["科目"],
        },
    )

    assert response.status_code == 200  # 整批不再 500
    rows = response.json()["preview_rows"]
    assert len(rows) > 0
    assert all(r["status"] == "parse_failed" for r in rows)  # 逐行降级而非整批崩


def test_duplicate_row_in_batch_flagged_as_duplicate_in_batch(client, upload_dir) -> None:
    """批次内两行数据完全相同时，第二行应被标注 DUPLICATE_IN_BATCH 异常码。"""
    # 构造含两行相同记录的 CSV（仅流水号不同，关键字段完全一致）。
    csv_bytes = (
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-01-01,,500.00,,9000.00,某公司,ACC001,货款,测试,TXN-DUP-1\n"
        "2026-01-01,,500.00,,9000.00,某公司,ACC001,货款,测试,TXN-DUP-2\n"
    ).encode()

    upload = client.post(
        "/api/files/upload",
        files={"file": ("dup_test.csv", csv_bytes, "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    response = client.post(
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
                    "余额": "balance",
                    "对方户名": "counterparty_name",
                    "对方账号": "counterparty_account_no",
                    "摘要": "summary",
                    "用途": "purpose",
                    "流水号": "bank_transaction_id",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [],
            "rules": [],
            "required_columns": [],
        },
    )

    assert response.status_code == 200
    rows = response.json()["preview_rows"]
    assert len(rows) == 2
    assert "DUPLICATE_IN_BATCH" not in rows[0]["exception_codes"]
    assert "DUPLICATE_IN_BATCH" in rows[1]["exception_codes"]


def test_no_orphan_bank_transaction_when_all_rows_fail_preview(client_with_db, tmp_path) -> None:
    """回归测试：build_preview_row 失败时不应留下孤儿 BankTransaction。

    Bad mapping (source field does not exist) causes build_preview_row to throw
    for every row, so every row lands in the except branch.  After the fix,
    db.add(bank_tx) is only called AFTER build_preview_row succeeds, so no
    BankTransaction rows should be persisted for the run.
    """
    import os

    from app.core.config import get_settings

    client, db = client_with_db

    # Override UPLOAD_DIR so the file upload succeeds.
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    get_settings.cache_clear()
    os.environ["UPLOAD_DIR"] = str(uploads)
    get_settings.cache_clear()

    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"
    upload = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", fixture.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    response = client.post(
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
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [
                {"target": "科目", "type": "field", "source": "不存在字段"},
            ],
            "rules": [],
            "required_columns": ["科目"],
        },
    )

    assert response.status_code == 200
    run_id = response.json()["id"]
    rows = response.json()["preview_rows"]
    assert len(rows) > 0
    assert all(r["status"] == "parse_failed" for r in rows)

    # Key regression assertion: no orphan BankTransaction rows for this run.
    count = db.query(BankTransaction).filter(BankTransaction.conversion_run_id == run_id).count()
    assert count == 0, (
        f"Expected 0 BankTransaction rows for run {run_id}, got {count}. "
        "Orphan bank_tx rows indicate db.add(bank_tx) was called before build_preview_row."
    )

    get_settings.cache_clear()


def test_balance_discontinuity_flagged(client, upload_dir) -> None:
    """余额跳变行应携带 BALANCE_DISCONTINUITY 异常码，连续行不应携带。"""
    # 行1: income=500, balance=1500 → 首行不判
    # 行2: income=300, balance=2300 → 预期 1500+300=1800，实际 2300 → 跳变
    # 行3: income=100, balance=2400 → 2300+100=2400 → 连续（基准更新为前行实际值）
    csv_bytes = (
        "交易日期,收入,支出,余额,摘要,流水号\n"
        "2026-01-01,500.00,,1500.00,货款,TXN-BAL-1\n"
        "2026-01-02,300.00,,2300.00,货款,TXN-BAL-2\n"
        "2026-01-03,100.00,,2400.00,货款,TXN-BAL-3\n"
    ).encode()

    upload = client.post(
        "/api/files/upload",
        files={"file": ("balance_jump.csv", csv_bytes, "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()

    response = client.post(
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
                    "余额": "balance",
                    "摘要": "summary",
                    "流水号": "bank_transaction_id",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [],
            "rules": [],
            "required_columns": [],
        },
    )

    assert response.status_code == 200
    rows = response.json()["preview_rows"]
    assert len(rows) == 3

    codes_row0 = rows[0]["exception_codes"]
    codes_row1 = rows[1]["exception_codes"]
    codes_row2 = rows[2]["exception_codes"]

    assert "BALANCE_DISCONTINUITY" not in codes_row0, "首行不应标注余额跳变"
    assert "BALANCE_DISCONTINUITY" in codes_row1, "第二行余额跳变应被标注"
    assert "BALANCE_DISCONTINUITY" not in codes_row2, "第三行余额连续不应标注"
