from decimal import Decimal

import pytest

from app.core.enums import TransactionDirection
from app.schemas.standard import StandardBankTransaction
from app.services.mapping_service import apply_mappings


def _transaction(**overrides: object) -> StandardBankTransaction:
    data = {
        "transaction_date": "2026-06-01",
        "posting_date": "2026-06-01",
        "bank_account_id": "bank-account-1",
        "currency": "CNY",
        "direction": TransactionDirection.CREDIT,
        "debit_amount": None,
        "credit_amount": Decimal("12000.00"),
        "net_amount": Decimal("12000.00"),
        "balance": Decimal("98000.00"),
        "counterparty_name": "某客户有限公司",
        "counterparty_account_no": "6222000000000000",
        "counterparty_bank_name": None,
        "summary": "货款",
        "purpose": "6月服务费",
        "transaction_type": "转账",
        "bank_transaction_id": "TXN001",
        "receipt_no": None,
        "source_file_id": "file-1",
        "source_sheet_name": "Sheet1",
        "source_row_index": 2,
        "raw_row": {},
    }
    data.update(overrides)
    return StandardBankTransaction(**data)


def test_apply_direct_fixed_and_concat_mappings() -> None:
    transaction = _transaction()
    mappings = [
        {"target": "日期", "type": "field", "source": "transaction_date"},
        {"target": "币种", "type": "fixed", "value": "人民币"},
        {
            "target": "备注",
            "type": "concat",
            "sources": ["summary", "purpose"],
            "separator": " - ",
        },
    ]

    result = apply_mappings(transaction, mappings, rule_outputs={})

    assert result == {"日期": "2026-06-01", "币种": "人民币", "备注": "货款 - 6月服务费"}


def test_apply_rule_output_and_manual_mappings() -> None:
    mappings = [
        {"target": "科目", "type": "rule_output", "source": "account_title"},
        {"target": "辅助核算", "type": "manual"},
    ]

    result = apply_mappings(
        _transaction(),
        mappings,
        rule_outputs={"account_title": "主营业务收入"},
    )

    assert result == {"科目": "主营业务收入", "辅助核算": None}


def test_missing_rule_output_returns_none_for_preview_validation() -> None:
    mappings = [{"target": "科目", "type": "rule_output", "source": "account_title"}]

    result = apply_mappings(_transaction(), mappings, rule_outputs={})

    assert result == {"科目": None}


def test_amount_field_mapping_returns_json_safe_value() -> None:
    mappings = [{"target": "贷方金额", "type": "field", "source": "credit_amount"}]

    result = apply_mappings(_transaction(), mappings, rule_outputs={})

    assert result == {"贷方金额": "12000.00"}
    assert not isinstance(result["贷方金额"], Decimal)


def test_concat_ignores_none_and_empty_string_values() -> None:
    transaction = _transaction(counterparty_bank_name=None, purpose="", receipt_no="R001")
    mappings = [
        {
            "target": "备注",
            "type": "concat",
            "sources": ["summary", "counterparty_bank_name", "purpose", "receipt_no"],
            "separator": "/",
        }
    ]

    result = apply_mappings(transaction, mappings, rule_outputs={})

    assert result == {"备注": "货款/R001"}


def test_unknown_mapping_type_raises_value_error() -> None:
    mappings = [{"target": "日期", "type": "computed", "source": "transaction_date"}]

    with pytest.raises(ValueError, match="Unsupported mapping type: computed"):
        apply_mappings(_transaction(), mappings, rule_outputs={})


def test_unknown_field_source_raises_value_error() -> None:
    mappings = [{"target": "日期", "type": "field", "source": "missing_date"}]

    with pytest.raises(ValueError, match="日期.*missing_date"):
        apply_mappings(_transaction(), mappings, rule_outputs={})


def test_concat_unknown_source_raises_value_error() -> None:
    mappings = [
        {
            "target": "备注",
            "type": "concat",
            "sources": ["summary", "missing_purpose"],
            "separator": "/",
        }
    ]

    with pytest.raises(ValueError, match="备注.*missing_purpose"):
        apply_mappings(_transaction(), mappings, rule_outputs={})
