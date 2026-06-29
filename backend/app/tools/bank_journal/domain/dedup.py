from __future__ import annotations

import hashlib

from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.enums import ExceptionCode
from app.tools.bank_journal.schemas.standard import StandardBankTransaction

_DEFAULT_KEY_FIELDS = ["transaction_date", "net_amount", "summary", "counterparty_account_no"]


def row_hash(txn: StandardBankTransaction, key_fields: list[str] | None = None) -> str:
    ctx = EvaluationContext.from_transaction(txn)
    fields = key_fields or _DEFAULT_KEY_FIELDS
    parts = [f"{k}={ctx.get(k)!r}" for k in fields]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def mark_duplicates(
    hashes: list[str], history: set[str]
) -> list[ExceptionCode | None]:
    seen: set[str] = set()
    result: list[ExceptionCode | None] = []
    for h in hashes:
        if h in seen:
            result.append(ExceptionCode.DUPLICATE_IN_BATCH)
        elif h in history:
            result.append(ExceptionCode.DUPLICATE_HISTORY)
        else:
            result.append(None)
        seen.add(h)
    return result
