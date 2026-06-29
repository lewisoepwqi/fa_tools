from decimal import Decimal

from app.tools.bank_journal.domain.dedup import mark_duplicates, row_hash
from app.tools.bank_journal.enums import ExceptionCode, TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def _txn(net):
    return StandardBankTransaction(
        transaction_date="2026-01-01", bank_account_id="acc-1",
        direction=TransactionDirection.CREDIT, net_amount=Decimal(net),
        summary="货款", source_file_id="f", source_sheet_name="S",
        source_row_index=2, raw_row={},
    )


def test_row_hash_stable_and_distinct():
    keys = ["transaction_date", "net_amount", "summary"]
    assert row_hash(_txn("100"), keys) == row_hash(_txn("100"), keys)
    assert row_hash(_txn("100"), keys) != row_hash(_txn("200"), keys)


def test_mark_duplicates_in_batch_and_history():
    hashes = ["a", "a", "b"]
    history = {"b"}
    result = mark_duplicates(hashes, history)
    assert result[0] is None
    assert result[1] == ExceptionCode.DUPLICATE_IN_BATCH
    assert result[2] == ExceptionCode.DUPLICATE_HISTORY
