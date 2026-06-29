"""TDD tests: anomaly codes must force NEEDS_CONFIRMATION even when rule allows auto-confirm.

Project principle: 不确定项默认进入人工确认(保守).
Rows carrying AMOUNT_DIRECTION_MISMATCH, DUPLICATE_IN_BATCH, DUPLICATE_HISTORY, or
BALANCE_DISCONTINUITY must NEVER end up as auto_confirmed, regardless of rule settings.

These tests are written RED-first (they will fail before the downgrade is applied in
conversion_service.py) and GREEN after.
"""

import pytest

from app.core.config import get_settings


@pytest.fixture()
def upload_dir(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield tmp_path / "uploads"
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_INLINE_PARSE_CONFIG = {
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
}

# Rule that matches on summary contains "货款" AND allows auto-confirm.
_AUTO_CONFIRM_RULE = {
    "id": "rule-auto",
    "version_id": "rule-version-auto",
    "priority": 10,
    "conditions": {"all": [{"field": "summary", "op": "contains", "value": "货款"}]},
    "actions": [{"field": "journal_summary", "value": "货款收入"}],
    "allow_auto_confirm": True,
}


def _upload(client, csv_bytes: bytes, filename: str = "test.csv") -> str:
    resp = client.post(
        "/api/files/upload",
        files={"file": (filename, csv_bytes, "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _run_conversion(client, source_file_id: str, rules: list, required_columns: list | None = None):
    return client.post(
        "/api/tools/bank-journal/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_parse_config": _INLINE_PARSE_CONFIG,
            "mappings": [],
            "rules": rules,
            "required_columns": required_columns or [],
        },
    )


# ---------------------------------------------------------------------------
# run_conversion tests
# ---------------------------------------------------------------------------


def test_amount_direction_mismatch_with_auto_confirm_rule_forces_needs_confirmation(
    client, upload_dir
) -> None:
    """A negative-income row generates AMOUNT_DIRECTION_MISMATCH AFTER status is set.

    Even though the matching rule has allow_auto_confirm=True, the presence of
    AMOUNT_DIRECTION_MISMATCH must downgrade the row to needs_confirmation.

    RED before fix: status would be auto_confirmed.
    GREEN after fix: status is needs_confirmation.
    """
    # Negative income (-12000.00) → parser emits AMOUNT_DIRECTION_MISMATCH warning.
    csv_bytes = (
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,-12000.00,,98000.00,某客户,6222000000000000,货款,6月服务费,TXN-NEG-1\n"
    ).encode()

    source_file_id = _upload(client, csv_bytes, "neg_income.csv")
    response = _run_conversion(client, source_file_id, [_AUTO_CONFIRM_RULE])

    assert response.status_code == 200, response.text
    rows = response.json()["preview_rows"]
    assert len(rows) == 1

    row = rows[0]
    assert "AMOUNT_DIRECTION_MISMATCH" in row["exception_codes"], (
        f"Expected AMOUNT_DIRECTION_MISMATCH in exception_codes, got {row['exception_codes']}"
    )
    assert row["status"] == "needs_confirmation", (
        f"Row with AMOUNT_DIRECTION_MISMATCH must not be auto_confirmed; got {row['status']}"
    )


def test_duplicate_in_batch_with_auto_confirm_rule_forces_needs_confirmation(
    client, upload_dir
) -> None:
    """The second of two identical rows gets DUPLICATE_IN_BATCH in the dedup post-pass.

    Even though both rows match a rule with allow_auto_confirm=True, the duplicate
    row must be downgraded to needs_confirmation after the dedup pass adds the code.

    RED before fix: second row status would be auto_confirmed.
    GREEN after fix: second row status is needs_confirmation.
    """
    # Two rows with identical key fields (date, net_amount, summary, counterparty_account_no).
    csv_bytes = (
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,500.00,,9000.00,某公司,ACC-DUP,货款,测试,TXN-DUP-A\n"
        "2026-06-01,2026-06-01,500.00,,9000.00,某公司,ACC-DUP,货款,测试,TXN-DUP-B\n"
    ).encode()

    source_file_id = _upload(client, csv_bytes, "dup_auto.csv")
    response = _run_conversion(client, source_file_id, [_AUTO_CONFIRM_RULE])

    assert response.status_code == 200, response.text
    rows = response.json()["preview_rows"]
    assert len(rows) == 2

    # First row: unique → auto_confirmed (no downgrade codes)
    assert rows[0]["status"] == "auto_confirmed", (
        f"First unique row should be auto_confirmed, got {rows[0]['status']}"
    )
    assert "DUPLICATE_IN_BATCH" not in rows[0]["exception_codes"]

    # Second row: duplicate → must be needs_confirmation
    assert "DUPLICATE_IN_BATCH" in rows[1]["exception_codes"], (
        f"Expected DUPLICATE_IN_BATCH in second row, got {rows[1]['exception_codes']}"
    )
    assert rows[1]["status"] == "needs_confirmation", (
        f"Duplicate row must not be auto_confirmed; got {rows[1]['status']}"
    )


# ---------------------------------------------------------------------------
# dry_run_conversion test
# ---------------------------------------------------------------------------


def _create_bank_template_for_dry_run(client) -> str:
    response = client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中行CSV(下载测试)",
            "bank_account_id": "bank-account-1",
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"sheet_name": "Sheet1"},
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
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_auto_confirm_rule(client) -> str:
    """Create a rule in DB: summary contains '货款', allow_auto_confirm=True."""
    response = client.post(
        "/api/tools/bank-journal/rules",
        json={
            "company_id": "company-1",
            "name": "货款自动确认规则",
            "version": {
                "priority": 10,
                "conditions_json": {
                    "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                },
                "actions_json": {"set": {"journal_summary": "货款收入"}},
                "allow_auto_confirm": True,
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_dry_run_amount_direction_mismatch_forces_needs_confirmation(
    client, upload_dir
) -> None:
    """In dry_run, AMOUNT_DIRECTION_MISMATCH warning added post-build_preview_row must
    downgrade AUTO_CONFIRMED to needs_confirmation.

    RED before fix: status would be auto_confirmed.
    GREEN after fix: status is needs_confirmation.
    """
    # Negative income → AMOUNT_DIRECTION_MISMATCH warning from parser.
    csv_bytes = (
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,-12000.00,,98000.00,某客户,6222000000000000,货款,6月服务费,TXN-DRY-NEG\n"
    ).encode()

    source_file_id = _upload(client, csv_bytes, "dry_neg.csv")
    bank_id = _create_bank_template_for_dry_run(client)
    rule_id = _create_auto_confirm_rule(client)

    response = client.post(
        "/api/tools/bank-journal/conversion-runs/dry-run",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
            "rule_ids": [rule_id],
        },
    )
    assert response.status_code == 200, response.text
    rows = response.json()["preview_rows"]
    assert len(rows) == 1

    row = rows[0]
    assert "AMOUNT_DIRECTION_MISMATCH" in row["exception_codes"], (
        "Expected AMOUNT_DIRECTION_MISMATCH in dry-run exception codes, "
        f"got {row['exception_codes']}"
    )
    assert row["status"] == "needs_confirmation", (
        "Dry-run row with AMOUNT_DIRECTION_MISMATCH must not be auto_confirmed; "
        f"got {row['status']}"
    )
