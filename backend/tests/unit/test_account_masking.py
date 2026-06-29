"""Task 12: 账号展示脱敏——对手账号在 apply_mappings 输出中脱敏。

暴露点：apply_mappings(mapping_service.py) 在 mapping type="field" 时把
counterparty_account_no 的明文值写入 output_values。该 dict 直接进入：
  - API 响应（JournalPreviewRowData.output_values）
  - DB 存储（output_values_json → 导出 CSV/XLSX 时直接读取）
修复：在 apply_mappings 内，source == "counterparty_account_no" 时对值调用
mask_account() 再放入 mapped_values。
"""

from decimal import Decimal

from app.tools.bank_journal.enums import TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.mapping_service import apply_mappings


def _txn(**overrides: object) -> StandardBankTransaction:
    data = {
        "transaction_date": "2026-06-01",
        "posting_date": "2026-06-01",
        "bank_account_id": "bank-1",
        "currency": "CNY",
        "direction": TransactionDirection.CREDIT,
        "debit_amount": None,
        "credit_amount": Decimal("100.00"),
        "net_amount": Decimal("100.00"),
        "balance": Decimal("1000.00"),
        "counterparty_name": "某客户",
        "counterparty_account_no": "6222021234567890",
        "counterparty_bank_name": None,
        "summary": "货款",
        "purpose": None,
        "transaction_type": None,
        "bank_transaction_id": "TXN001",
        "receipt_no": None,
        "source_file_id": "file-1",
        "source_sheet_name": "Sheet1",
        "source_row_index": 2,
        "raw_row": {},
    }
    data.update(overrides)
    return StandardBankTransaction(**data)


def test_counterparty_account_no_masked_in_output_values() -> None:
    """对手账号作为映射源时，output_values 中应显示脱敏值而非明文。"""
    txn = _txn(counterparty_account_no="6222021234567890")
    mappings = [
        {"target": "对方账号", "type": "field", "source": "counterparty_account_no"},
    ]

    result = apply_mappings(txn, mappings, rule_outputs={})

    # 脱敏后应为 ****7890，不得是明文
    assert result["对方账号"] == "****7890", (
        f"期望脱敏值 ****7890，实际得到 {result['对方账号']!r}"
    )
    assert "6222021234567890" not in str(result.values()), "output_values 中出现了明文账号"


def test_counterparty_account_no_short_masked() -> None:
    """≤4 位账号脱敏为 ****。"""
    txn = _txn(counterparty_account_no="1234")
    mappings = [
        {"target": "对方账号", "type": "field", "source": "counterparty_account_no"},
    ]

    result = apply_mappings(txn, mappings, rule_outputs={})

    assert result["对方账号"] == "****"


def test_counterparty_account_no_none_stays_none() -> None:
    """counterparty_account_no 为 None 时输出也为 None（mask_account(None) == None）。"""
    txn = _txn(counterparty_account_no=None)
    mappings = [
        {"target": "对方账号", "type": "field", "source": "counterparty_account_no"},
    ]

    result = apply_mappings(txn, mappings, rule_outputs={})

    assert result["对方账号"] is None


def test_other_fields_not_affected_by_masking() -> None:
    """其他字段（摘要、对方户名）不受账号脱敏影响。"""
    txn = _txn()
    mappings = [
        {"target": "摘要", "type": "field", "source": "summary"},
        {"target": "对方户名", "type": "field", "source": "counterparty_name"},
        {"target": "对方账号", "type": "field", "source": "counterparty_account_no"},
    ]

    result = apply_mappings(txn, mappings, rule_outputs={})

    assert result["摘要"] == "货款"
    assert result["对方户名"] == "某客户"
    assert result["对方账号"] == "****7890"
