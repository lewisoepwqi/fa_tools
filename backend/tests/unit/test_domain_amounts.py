from decimal import Decimal

import pytest

from app.tools.bank_journal.domain.amounts import AmountError, SignedAmount
from app.tools.bank_journal.enums import TransactionDirection


def test_income_credit_positive():
    sa = SignedAmount.from_income_expense(Decimal("100"), None)
    assert sa.direction == TransactionDirection.CREDIT
    assert sa.net_amount == Decimal("100")
    assert sa.credit_amount == Decimal("100")
    assert sa.debit_amount is None
    assert sa.sign_anomaly is False


def test_expense_debit_negative_net():
    sa = SignedAmount.from_income_expense(None, Decimal("80"))
    assert sa.direction == TransactionDirection.DEBIT
    assert sa.net_amount == Decimal("-80")
    assert sa.debit_amount == Decimal("80")


def test_negative_income_flips_direction_and_flags_anomaly():
    # 收入栏填负数(冲账)→ 方向翻成借,magnitude 取绝对值,net 与方向一致,且标记异常
    sa = SignedAmount.from_income_expense(Decimal("-50"), None)
    assert sa.direction == TransactionDirection.DEBIT
    assert sa.magnitude == Decimal("50")
    assert sa.net_amount == Decimal("-50")
    assert sa.sign_anomaly is True


def test_both_columns_populated_raises():
    with pytest.raises(AmountError):
        SignedAmount.from_income_expense(Decimal("1"), Decimal("2"))


def test_signed_amount_factory():
    assert SignedAmount.from_signed(Decimal("-5")).direction == TransactionDirection.DEBIT
    assert SignedAmount.from_signed(Decimal("5")).direction == TransactionDirection.CREDIT
