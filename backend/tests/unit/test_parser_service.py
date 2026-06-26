from decimal import Decimal

from app.core.enums import TransactionDirection
from app.schemas.standard import StandardBankTransaction


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
