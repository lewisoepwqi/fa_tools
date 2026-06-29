from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.tools.bank_journal.enums import TransactionDirection

_ZERO = Decimal("0")


class AmountError(ValueError):
    """金额无法确定方向或双栏冲突。继承 ValueError 以兼容现有 except 捕获。"""


@dataclass(frozen=True)
class SignedAmount:
    magnitude: Decimal  # 恒 >= 0
    direction: TransactionDirection
    sign_anomaly: bool = False  # 原始值为负导致方向翻转,供上层标记 AMOUNT_DIRECTION_MISMATCH

    @property
    def net_amount(self) -> Decimal:
        return self.magnitude if self.direction == TransactionDirection.CREDIT else -self.magnitude

    @property
    def debit_amount(self) -> Decimal | None:
        return self.magnitude if self.direction == TransactionDirection.DEBIT else None

    @property
    def credit_amount(self) -> Decimal | None:
        return self.magnitude if self.direction == TransactionDirection.CREDIT else None

    @classmethod
    def _normalize(cls, value: Decimal, base: TransactionDirection) -> SignedAmount:
        if value < _ZERO:
            flipped = (
                TransactionDirection.DEBIT
                if base == TransactionDirection.CREDIT
                else TransactionDirection.CREDIT
            )
            return cls(magnitude=-value, direction=flipped, sign_anomaly=True)
        return cls(magnitude=value, direction=base)

    @classmethod
    def from_income_expense(
        cls, income: Decimal | None, expense: Decimal | None
    ) -> SignedAmount:
        inc = income or _ZERO
        exp = expense or _ZERO
        if inc != _ZERO and exp != _ZERO:
            raise AmountError("Both income and expense amounts are populated")
        if inc != _ZERO:
            return cls._normalize(inc, TransactionDirection.CREDIT)
        if exp != _ZERO:
            return cls._normalize(exp, TransactionDirection.DEBIT)
        raise AmountError("Unable to determine transaction amount")

    @classmethod
    def from_debit_credit(cls, debit: Decimal | None, credit: Decimal | None) -> SignedAmount:
        deb = debit or _ZERO
        cre = credit or _ZERO
        if deb != _ZERO and cre != _ZERO:
            raise AmountError("Both debit and credit amounts are populated")
        if cre != _ZERO:
            return cls._normalize(cre, TransactionDirection.CREDIT)
        if deb != _ZERO:
            return cls._normalize(deb, TransactionDirection.DEBIT)
        raise AmountError("Unable to determine transaction amount")

    @classmethod
    def from_amount_with_direction(
        cls, amount: Decimal, direction: TransactionDirection
    ) -> SignedAmount:
        return cls(magnitude=abs(amount), direction=direction)

    @classmethod
    def from_signed(cls, amount: Decimal) -> SignedAmount:
        if amount >= _ZERO:
            return cls(magnitude=amount, direction=TransactionDirection.CREDIT)
        return cls(magnitude=-amount, direction=TransactionDirection.DEBIT)
