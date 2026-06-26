from decimal import Decimal
from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.core.enums import AmountMode, TransactionDirection
from app.schemas.standard import StandardBankTransaction
from app.services.parser_service import (
    BankTemplateParseConfig,
    detect_header_row,
    parse_bank_statement,
)


def _base_config(file_type: str) -> BankTemplateParseConfig:
    return BankTemplateParseConfig(
        bank_account_id="bank-account-1",
        source_file_id="file-1",
        file_type=file_type,
        sheet_name="Sheet1",
        header_row_index=0,
        data_start_row_index=1,
        field_aliases={
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
        amount_mode=AmountMode.INCOME_EXPENSE_COLUMNS,
        amount_config={"income": "income_amount", "expense": "expense_amount"},
        date_formats=["%Y-%m-%d"],
    )


def test_standard_bank_transaction_accepts_credit_amount() -> None:
    transaction = StandardBankTransaction(
        transaction_date="2026-06-01",
        posting_date="2026-06-01",
        bank_account_id="bank-account-1",
        currency="CNY",
        direction=TransactionDirection.CREDIT,
        debit_amount=None,
        credit_amount=Decimal("12000.00"),
        net_amount=Decimal("12000.00"),
        balance=Decimal("98000.00"),
        counterparty_name="某客户有限公司",
        counterparty_account_no="6222000000000000",
        counterparty_bank_name="某银行某支行",
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="202606010001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={"收入": "12000.00"},
    )

    assert transaction.direction == TransactionDirection.CREDIT
    assert transaction.net_amount == Decimal("12000.00")


def test_detect_header_row_from_csv_preview() -> None:
    rows = [
        ["中国银行交易流水"],
        ["交易日期", "入账日期", "收入", "支出", "余额", "对方户名", "摘要"],
        ["2026-06-01", "2026-06-01", "12000.00", "", "98000.00", "某客户有限公司", "货款"],
    ]

    assert detect_header_row(rows) == 1


def test_parse_csv_statement_to_standard_transactions() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"
    config = _base_config("csv")

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 2
    assert transactions[0].direction == TransactionDirection.CREDIT
    assert transactions[0].net_amount == Decimal("12000.00")
    assert transactions[1].direction == TransactionDirection.DEBIT
    assert transactions[1].net_amount == Decimal("-3000.00")


def test_parse_xlsx_statement_to_standard_transactions() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.xlsx"
    config = _base_config("xlsx")

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 2
    assert transactions[0].direction == TransactionDirection.CREDIT
    assert transactions[0].net_amount == Decimal("12000.00")
    assert transactions[1].direction == TransactionDirection.DEBIT
    assert transactions[1].net_amount == Decimal("-3000.00")


def test_parse_xlsx_statement_with_native_excel_dates(tmp_path: Path) -> None:
    fixture = tmp_path / "bank_statement_native_dates.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["交易日期", "入账日期", "收入", "支出", "余额", "对方户名", "对方账号", "摘要", "用途", "流水号"])
    sheet.append([date(2026, 6, 1), date(2026, 6, 1), "12000.00", "", "98000.00", "某客户有限公司", "6222000000000000", "货款", "6月服务费", "TXN001"])
    sheet.append([date(2026, 6, 2), date(2026, 6, 2), "", "3000.00", "95000.00", "某供应商有限公司", "6222111111111111", "采购款", "办公用品", "TXN002"])
    sheet.append(["", "", "", "", "", "", "", "", "", ""])
    workbook.save(fixture)

    transactions = parse_bank_statement(fixture, _base_config("xlsx"))

    assert len(transactions) == 2
    assert transactions[0].transaction_date == "2026-06-01"
    assert transactions[1].transaction_date == "2026-06-02"
    assert transactions[1].net_amount == Decimal("-3000.00")


def test_parse_bank_statement_raises_for_both_income_and_expense_populated(tmp_path: Path) -> None:
    fixture = tmp_path / "both_amounts.csv"
    fixture.write_text(
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,12000.00,3000.00,98000.00,某客户有限公司,6222000000000000,货款,6月服务费,TXN001\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Both income and expense amounts are populated"):
        parse_bank_statement(fixture, _base_config("csv"))


def test_parse_bank_statement_raises_for_invalid_amount(tmp_path: Path) -> None:
    fixture = tmp_path / "invalid_amount.csv"
    fixture.write_text(
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,12x00.00,,98000.00,某客户有限公司,6222000000000000,货款,6月服务费,TXN001\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid amount"):
        parse_bank_statement(fixture, _base_config("csv"))


def test_parse_bank_statement_raises_for_missing_sheet(tmp_path: Path) -> None:
    fixture = tmp_path / "missing_sheet.xlsx"
    workbook = Workbook()
    workbook.active.title = "OtherSheet"
    workbook.save(fixture)

    with pytest.raises(ValueError, match="Sheet not found: Sheet1"):
        parse_bank_statement(fixture, _base_config("xlsx"))


def test_parse_bank_statement_raises_for_unsupported_xls_file_type() -> None:
    with pytest.raises(ValueError, match="Unsupported file type: xls"):
        parse_bank_statement(Path("ignored.xls"), _base_config("xls"))
