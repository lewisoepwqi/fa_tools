from decimal import Decimal

from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.enums import TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def _txn(**overrides):
    base = dict(
        transaction_date="2026-01-01",
        bank_account_id="acc-1",
        direction=TransactionDirection.CREDIT,
        net_amount=Decimal("100"),
        extra_fields={"cost_center": "CC-01"},
        source_file_id="f-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )
    base.update(overrides)
    return StandardBankTransaction(**base)


def test_standard_field_accessible():
    ctx = EvaluationContext.from_transaction(_txn())
    assert ctx.get("net_amount") == Decimal("100")
    assert ctx.has("direction") is True


def test_custom_field_flattened_to_top_level():
    # 治本 #2:扩展字段与标准字段同权,直接用 field_key 取到
    ctx = EvaluationContext.from_transaction(_txn())
    assert ctx.get("cost_center") == "CC-01"
    assert ctx.has("cost_center") is True
    assert "extra_fields" not in ctx.as_dict()


def test_missing_field_returns_none():
    ctx = EvaluationContext.from_transaction(_txn())
    assert ctx.get("nonexistent") is None
    assert ctx.has("nonexistent") is False
