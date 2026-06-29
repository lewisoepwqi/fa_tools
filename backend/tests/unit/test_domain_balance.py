from decimal import Decimal

from app.tools.bank_journal.domain.balance import check_balance_continuity


def test_continuous_balance_no_flag():
    rows = [
        (Decimal("100"), Decimal("100")),  # 首行不判
        (Decimal("150"), Decimal("50")),   # 100 + 50 = 150 ✓
        (Decimal("120"), Decimal("-30")),  # 150 - 30 = 120 ✓
    ]
    assert check_balance_continuity(rows) == [False, False, False]


def test_discontinuity_flagged():
    rows = [
        (Decimal("100"), Decimal("100")),
        (Decimal("999"), Decimal("50")),   # 期望 150,实际 999 → 跳变
    ]
    assert check_balance_continuity(rows) == [False, True]


def test_missing_balance_not_flagged():
    rows = [(Decimal("100"), Decimal("100")), (None, Decimal("50"))]
    assert check_balance_continuity(rows) == [False, False]
