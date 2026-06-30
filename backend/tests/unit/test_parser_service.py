import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.tools.bank_journal.domain.amounts import SignedAmount
from app.tools.bank_journal.enums import AmountMode, ExceptionCode, TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.parser_service import (
    BankTemplateParseConfig,
    _decimal_or_none,
    _parse_amounts,
    _read_rows,
    detect_bank_template_config,
    detect_header_row,
    parse_bank_rows,
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
    sheet.append(
        [
            "交易日期", "入账日期", "收入", "支出", "余额",
            "对方户名", "对方账号", "摘要", "用途", "流水号",
        ]
    )
    sheet.append(
        [
            date(2026, 6, 1), date(2026, 6, 1), "12000.00", "",
            "98000.00", "某客户有限公司", "6222000000000000",
            "货款", "6月服务费", "TXN001",
        ]
    )
    sheet.append(
        [
            date(2026, 6, 2), date(2026, 6, 2), "", "3000.00",
            "95000.00", "某供应商有限公司", "6222111111111111",
            "采购款", "办公用品", "TXN002",
        ]
    )
    sheet.append(["", "", "", "", "", "", "", "", "", ""])
    workbook.save(fixture)

    transactions = parse_bank_statement(fixture, _base_config("xlsx"))

    assert len(transactions) == 2
    assert transactions[0].transaction_date == "2026-06-01"
    assert transactions[1].transaction_date == "2026-06-02"
    assert transactions[1].net_amount == Decimal("-3000.00")


def test_parse_bank_statement_raises_for_missing_sheet(tmp_path: Path) -> None:
    fixture = tmp_path / "missing_sheet.xlsx"
    workbook = Workbook()
    workbook.active.title = "OtherSheet"
    workbook.save(fixture)

    with pytest.raises(ValueError, match="Sheet not found: Sheet1"):
        parse_bank_statement(fixture, _base_config("xlsx"))


def test_parse_bank_statement_raises_for_header_out_of_range(tmp_path: Path) -> None:
    """表头行越界属于结构性错误（与单行无关），仍抛出。"""
    fixture = tmp_path / "empty.csv"
    fixture.write_text("仅一行\n", encoding="utf-8")
    config = _base_config("csv")
    config.header_row_index = 5

    with pytest.raises(ValueError, match="Header row index is out of range"):
        parse_bank_statement(fixture, config)


# ---------------------------------------------------------------------------
# P1-1: 逐行异常标记（不再因单行错误中断批次）
# ---------------------------------------------------------------------------


def test_parse_rows_marks_invalid_amount_without_aborting(tmp_path: Path) -> None:
    """金额无法解析：该行标记 INVALID_AMOUNT，其余行继续解析。"""
    fixture = tmp_path / "invalid_amount.csv"
    fixture.write_text(
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,12x00.00,,98000.00,某客户有限公司,6222000000000000,货款,6月服务费,TXN001\n"
        "2026-06-02,2026-06-02,,3000.00,95000.00,某供应商有限公司,6222111111111111,采购款,办公用品,TXN002\n",
        encoding="utf-8",
    )
    rows = parse_bank_rows(fixture, _base_config("csv"))

    assert len(rows) == 2
    assert rows[0].transaction is None
    assert ExceptionCode.INVALID_AMOUNT in rows[0].parse_errors
    assert rows[0].source_row_index == 2
    # 第二行不受影响，正常解析
    assert rows[1].transaction is not None
    assert rows[1].parse_errors == []


def test_parse_rows_marks_invalid_date_without_aborting(tmp_path: Path) -> None:
    """日期无法解析：该行标记 INVALID_DATE，其余行继续。"""
    fixture = tmp_path / "invalid_date.csv"
    fixture.write_text(
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "not-a-date,2026-06-01,12000.00,,98000.00,某客户有限公司,6222000000000000,货款,6月服务费,TXN001\n"
        "2026-06-02,2026-06-02,,3000.00,95000.00,某供应商有限公司,6222111111111111,采购款,办公用品,TXN002\n",
        encoding="utf-8",
    )
    rows = parse_bank_rows(fixture, _base_config("csv"))

    assert len(rows) == 2
    assert rows[0].transaction is None
    assert ExceptionCode.INVALID_DATE in rows[0].parse_errors
    assert rows[1].transaction is not None


def test_parse_rows_marks_missing_required_date_field(tmp_path: Path) -> None:
    """交易日期缺失：标记 MISSING_REQUIRED_FIELD。"""
    fixture = tmp_path / "missing_date.csv"
    fixture.write_text(
        "交易日期,入账日期,收入,支出,余额,对方户名,摘要\n"
        ",2026-06-01,12000.00,,98000.00,某客户有限公司,货款\n",
        encoding="utf-8",
    )
    rows = parse_bank_rows(fixture, _base_config("csv"))

    assert len(rows) == 1
    assert rows[0].transaction is None
    assert ExceptionCode.MISSING_REQUIRED_FIELD in rows[0].parse_errors
    # 失败行仍保留原始行快照用于追溯
    assert rows[0].raw_row is not None


# ---------------------------------------------------------------------------
# P1-7: 表头自动识别接线
# ---------------------------------------------------------------------------


def test_detect_bank_template_config_from_sample(tmp_path: Path) -> None:
    """从样本文件自动识别模板配置（PRD §5.1.3）。"""
    fixture = tmp_path / "sample_with_title.csv"
    fixture.write_text(
        "中国银行交易流水明细\n"
        "交易日期,入账日期,收入,支出,余额,对方户名,对方账号,摘要,用途,流水号\n"
        "2026-06-01,2026-06-01,12000.00,,98000.00,某客户有限公司,6222000000000000,货款,6月服务费,TXN001\n",
        encoding="utf-8",
    )

    detected = detect_bank_template_config(fixture, "csv")

    # 第一行是标题，表头在第 1 行
    assert detected["header_row_index"] == 1
    assert detected["data_start_row_index"] == 2
    assert detected["field_aliases"]["交易日期"] == "transaction_date"
    assert detected["field_aliases"]["收入"] == "income_amount"
    assert detected["field_aliases"]["支出"] == "expense_amount"
    assert detected["amount_mode"] == "income_expense_columns"
    assert detected["amount_config"] == {
        "income": "income_amount",
        "expense": "expense_amount",
    }
    assert "%Y-%m-%d" in detected["date_formats"]


def test_detect_amount_mode_debit_credit_columns(tmp_path: Path) -> None:
    fixture = tmp_path / "debit_credit_sample.csv"
    fixture.write_text(
        "交易日期,借方发生额,贷方发生额,对方户名,摘要\n"
        "2026-06-01,,12000.00,某客户有限公司,货款\n",
        encoding="utf-8",
    )

    detected = detect_bank_template_config(fixture, "csv")

    assert detected["amount_mode"] == "debit_credit_columns"
    assert detected["amount_config"] == {
        "debit": "debit_amount",
        "credit": "credit_amount",
    }


def test_parse_bank_statement_raises_for_unsupported_xls_file_type() -> None:
    with pytest.raises(ValueError, match="Unsupported file type: xls"):
        parse_bank_statement(Path("ignored.xls"), _base_config("xls"))


# ---------------------------------------------------------------------------
# P1-2: 三种缺失的金额模式
# ---------------------------------------------------------------------------


def _config_with(
    file_type: str,
    amount_mode: AmountMode,
    amount_config: dict[str, str],
    field_aliases: dict[str, str],
    date_formats: list[str] | None = None,
) -> BankTemplateParseConfig:
    return BankTemplateParseConfig(
        bank_account_id="bank-account-1",
        source_file_id="file-1",
        file_type=file_type,
        sheet_name="Sheet1",
        header_row_index=0,
        data_start_row_index=1,
        field_aliases=field_aliases,
        amount_mode=amount_mode,
        amount_config=amount_config,
        date_formats=date_formats or ["%Y-%m-%d"],
    )


def _write_csv(tmp_path: Path, name: str, header: str, *rows: str) -> Path:
    fixture = tmp_path / name
    fixture.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return fixture


def test_parse_single_amount_with_direction_credit(tmp_path: Path) -> None:
    """单金额列 + 方向列：方向=收入 → credit。"""
    fixture = _write_csv(
        tmp_path,
        "single_direction.csv",
        "交易日期,金额,方向,对方户名,摘要",
        "2026-06-01,12000.00,收入,某客户有限公司,货款",
    )
    config = _config_with(
        "csv",
        AmountMode.SINGLE_AMOUNT_WITH_DIRECTION,
        amount_config={"amount": "amount", "direction": "direction"},
        field_aliases={
            "交易日期": "transaction_date",
            "金额": "amount",
            "方向": "direction",
            "对方户名": "counterparty_name",
            "摘要": "summary",
        },
    )

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 1
    assert transactions[0].direction == TransactionDirection.CREDIT
    assert transactions[0].credit_amount == Decimal("12000.00")
    assert transactions[0].net_amount == Decimal("12000.00")


def test_parse_single_amount_with_direction_debit(tmp_path: Path) -> None:
    """单金额列 + 方向列：方向=支出 → debit。"""
    fixture = _write_csv(
        tmp_path,
        "single_direction_debit.csv",
        "交易日期,金额,方向,对方户名,摘要",
        "2026-06-02,3000.00,支出,某供应商有限公司,采购款",
    )
    config = _config_with(
        "csv",
        AmountMode.SINGLE_AMOUNT_WITH_DIRECTION,
        amount_config={"amount": "amount", "direction": "direction"},
        field_aliases={
            "交易日期": "transaction_date",
            "金额": "amount",
            "方向": "direction",
            "对方户名": "counterparty_name",
            "摘要": "summary",
        },
    )

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 1
    assert transactions[0].direction == TransactionDirection.DEBIT
    assert transactions[0].debit_amount == Decimal("3000.00")
    assert transactions[0].net_amount == Decimal("-3000.00")


def test_parse_debit_credit_columns(tmp_path: Path) -> None:
    """借方/贷方双列：贷方列有值 → credit，借方列有值 → debit。"""
    fixture = _write_csv(
        tmp_path,
        "debit_credit.csv",
        "交易日期,借方发生额,贷方发生额,对方户名,摘要",
        "2026-06-01,,12000.00,某客户有限公司,货款",
        "2026-06-02,3000.00,,某供应商有限公司,采购款",
    )
    config = _config_with(
        "csv",
        AmountMode.DEBIT_CREDIT_COLUMNS,
        amount_config={"debit": "debit_amount", "credit": "credit_amount"},
        field_aliases={
            "交易日期": "transaction_date",
            "借方发生额": "debit_amount",
            "贷方发生额": "credit_amount",
            "对方户名": "counterparty_name",
            "摘要": "summary",
        },
    )

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 2
    assert transactions[0].direction == TransactionDirection.CREDIT
    assert transactions[0].credit_amount == Decimal("12000.00")
    assert transactions[1].direction == TransactionDirection.DEBIT
    assert transactions[1].debit_amount == Decimal("3000.00")


def test_parse_signed_amount_positive_is_credit(tmp_path: Path) -> None:
    """带符号金额：正数 → credit。"""
    fixture = _write_csv(
        tmp_path,
        "signed_pos.csv",
        "交易日期,金额,对方户名,摘要",
        "2026-06-01,12000.00,某客户有限公司,货款",
    )
    config = _config_with(
        "csv",
        AmountMode.SIGNED_AMOUNT,
        amount_config={"amount": "amount"},
        field_aliases={
            "交易日期": "transaction_date",
            "金额": "amount",
            "对方户名": "counterparty_name",
            "摘要": "summary",
        },
    )

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 1
    assert transactions[0].direction == TransactionDirection.CREDIT
    assert transactions[0].net_amount == Decimal("12000.00")


def test_parse_signed_amount_negative_is_debit(tmp_path: Path) -> None:
    """带符号金额：负数 → debit。"""
    fixture = _write_csv(
        tmp_path,
        "signed_neg.csv",
        "交易日期,金额,对方户名,摘要",
        "2026-06-02,-3000.00,某供应商有限公司,采购款",
    )
    config = _config_with(
        "csv",
        AmountMode.SIGNED_AMOUNT,
        amount_config={"amount": "amount"},
        field_aliases={
            "交易日期": "transaction_date",
            "金额": "amount",
            "对方户名": "counterparty_name",
            "摘要": "summary",
        },
    )

    transactions = parse_bank_statement(fixture, config)

    assert len(transactions) == 1
    assert transactions[0].direction == TransactionDirection.DEBIT
    assert transactions[0].net_amount == Decimal("-3000.00")


def test_read_rows_decodes_gbk_csv(tmp_path):
    path = tmp_path / "gbk.csv"
    with path.open("w", encoding="gbk", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["日期", "摘要", "金额"])
        writer.writerow(["2026-01-01", "工资", "100"])
    rows = list(_read_rows(path, "csv", ""))  # 物化迭代器以供随机访问
    assert rows[0] == ["日期", "摘要", "金额"]
    assert rows[1][1] == "工资"


def test_read_rows_is_lazy_iterator(tmp_path):
    """_read_rows 返回惰性迭代器，不一次性物化整表。"""
    import types

    csv_path = tmp_path / "big.csv"
    csv_path.write_text("h1,h2\n" + "\n".join(f"a{i},b{i}" for i in range(1000)), encoding="utf-8")
    rows = _read_rows(str(csv_path), "csv", "")
    assert isinstance(rows, types.GeneratorType) or hasattr(rows, "__next__")
    first = next(iter(rows))
    assert first is not None


def test_decimal_cleaning_variants():
    assert _decimal_or_none("¥1,234.50") == Decimal("1234.50")
    assert _decimal_or_none("（1,000.00）") == Decimal("-1000.00")  # 全角括号负数
    assert _decimal_or_none("(1000)") == Decimal("-1000")
    assert _decimal_or_none("500 DR") == Decimal("-500")
    assert _decimal_or_none("500 CR") == Decimal("500")
    assert _decimal_or_none("１２３") == Decimal("123")  # 全角数字


# ---------------------------------------------------------------------------
# Task 9: _parse_amounts 返回 SignedAmount + 负数翻向告警
# ---------------------------------------------------------------------------


def test_parse_amounts_returns_signed_amount():
    sa = _parse_amounts(
        {"income": "100", "expense": ""},
        AmountMode.INCOME_EXPENSE_COLUMNS,
        {"income": "income", "expense": "expense"},
    )
    assert isinstance(sa, SignedAmount)
    assert sa.direction == TransactionDirection.CREDIT
    assert sa.net_amount == Decimal("100")


def test_parse_amounts_negative_income_flags_anomaly():
    sa = _parse_amounts(
        {"income": "-50", "expense": ""},
        AmountMode.INCOME_EXPENSE_COLUMNS,
        {"income": "income", "expense": "expense"},
    )
    assert sa.direction == TransactionDirection.DEBIT
    assert sa.net_amount == Decimal("-50")
    assert sa.sign_anomaly is True
