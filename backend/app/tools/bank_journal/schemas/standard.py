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
    # 公司级自定义扩展字段:field_key → 值。
    # 经 EvaluationContext.from_transaction() 拍平到顶层命名空间后,
    # 规则引擎/映射引擎即可用 field_key 与标准字段同等引用。
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    source_file_id: str
    source_sheet_name: str
    source_row_index: int = Field(ge=1)
    raw_row: dict[str, Any]
