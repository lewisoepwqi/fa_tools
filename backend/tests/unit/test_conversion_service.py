from decimal import Decimal

from app.tools.bank_journal.enums import ExceptionCode, PreviewStatus, TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.conversion_service import build_preview_row


def test_build_preview_row_requires_confirmation_when_required_field_missing() -> None:
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
        counterparty_bank_name=None,
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="TXN001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )

    row = build_preview_row(
        transaction=transaction,
        mappings=[{"target": "日期", "type": "field", "source": "transaction_date"}],
        rules=[],
        required_columns=["日期", "科目"],
        row_index=1,
    )

    assert row.status == PreviewStatus.NEEDS_CONFIRMATION
    assert ExceptionCode.MISSING_REQUIRED_FIELD in row.exception_codes
    assert row.output_values["日期"] == "2026-06-01"
