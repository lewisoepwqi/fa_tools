from __future__ import annotations

from decimal import Decimal


def check_balance_continuity(rows: list[tuple[Decimal | None, Decimal]]) -> list[bool]:
    """逐行判断余额是否连续。rows 按行序给出 (balance, net_amount)。

    规则:本行 balance 应 ≈ 上一行 balance + 本行 net_amount。
    首行、本行或上一行缺 balance 时不判(False)。
    """
    flags: list[bool] = []
    prev_balance: Decimal | None = None
    for balance, net in rows:
        if prev_balance is None or balance is None:
            flags.append(False)
        else:
            flags.append(balance != prev_balance + net)
        if balance is not None:
            prev_balance = balance
    return flags
