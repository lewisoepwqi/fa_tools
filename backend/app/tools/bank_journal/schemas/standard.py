from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.tools.bank_journal.enums import TransactionDirection


class StandardBankTransaction(BaseModel):
    transaction_date: str
    posting_date: str | None = None
    bank_account_id: str
    currency: str = "CNY"
    direction: TransactionDirection
    debit_amount: Decimal | None = None
    credit_amount: Decimal | None = None
    net_amount: Decimal
    balance: Decimal | None = None
    counterparty_name: str | None = None
    counterparty_account_no: str | None = None
    counterparty_bank_name: str | None = None
    summary: str | None = None
    purpose: str | None = None
    transaction_type: str | None = None
    bank_transaction_id: str | None = None
    receipt_no: str | None = None
    source_file_id: str
    source_sheet_name: str
    source_row_index: int = Field(ge=1)
    raw_row: dict[str, Any]
