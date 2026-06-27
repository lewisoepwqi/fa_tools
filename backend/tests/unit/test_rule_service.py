from decimal import Decimal

from app.core.enums import ExceptionCode, TransactionDirection
from app.schemas.standard import StandardBankTransaction
from app.services.rule_service import apply_rules


def _transaction() -> StandardBankTransaction:
    return StandardBankTransaction(
        transaction_date="2026-06-01",
        posting_date="2026-06-01",
        bank_account_id="bank-account-1",
        currency="CNY",
        direction=TransactionDirection.CREDIT,
        debit_amount=None,
        credit_amount=Decimal("12000.00"),
        net_amount=Decimal("12000.00"),
        balance=Decimal("98000.00"),
        counterparty_name="某客户有限公司",
        counterparty_account_no="6222000000000000",
        counterparty_bank_name=None,
        summary="货款",
        purpose="6月服务费",
        transaction_type="转账",
        bank_transaction_id="TXN001",
        receipt_no=None,
        source_file_id="file-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )


def test_apply_rules_returns_outputs_and_trace() -> None:
    rules = [
        {
            "id": "rule-1",
            "version_id": "rule-version-1",
            "priority": 10,
            "conditions": {
                "all": [
                    {"field": "direction", "op": "eq", "value": "credit"},
                    {"field": "summary", "op": "contains", "value": "货款"},
                ]
            },
            "actions": [
                {"field": "journal_summary", "value": "收到客户款项"},
                {"field": "account_subject", "value": "银行存款"},
            ],
            "allow_auto_confirm": False,
        }
    ]

    result = apply_rules(_transaction(), rules)

    assert result.outputs["journal_summary"] == "收到客户款项"
    assert result.outputs["account_subject"] == "银行存款"
    assert result.matched_rule_version_ids == ["rule-version-1"]
    assert result.exceptions == []


def test_apply_rules_marks_field_conflict() -> None:
    rules = [
        {
            "id": "rule-1",
            "version_id": "rule-version-1",
            "priority": 10,
            "conditions": {"all": [{"field": "summary", "op": "contains", "value": "货款"}]},
            "actions": [{"field": "account_subject", "value": "银行存款"}],
            "allow_auto_confirm": False,
        },
        {
            "id": "rule-2",
            "version_id": "rule-version-2",
            "priority": 20,
            "conditions": {
                "all": [{"field": "counterparty_name", "op": "contains", "value": "客户"}]
            },
            "actions": [{"field": "account_subject", "value": "应收账款"}],
            "allow_auto_confirm": False,
        },
    ]

    result = apply_rules(_transaction(), rules)

    assert ExceptionCode.RULE_CONFLICT in result.exceptions
    assert result.conflicts["account_subject"] == ["银行存款", "应收账款"]


def _single_condition_rule(condition: dict) -> list[dict]:
    return [
        {
            "id": "rule-1",
            "version_id": "rule-version-1",
            "priority": 10,
            "conditions": {"all": [condition]},
            "actions": [{"field": "account_subject", "value": "银行存款"}],
            "allow_auto_confirm": False,
        }
    ]


def test_gte_on_none_field_does_not_match_and_does_not_crash() -> None:
    """P1-4: 可选字段（如 balance）为 None 时 gte 应安全地不匹配。"""
    transaction = _transaction()
    transaction.balance = None

    result = apply_rules(
        transaction, _single_condition_rule({"field": "balance", "op": "gte", "value": "100"})
    )

    assert result.matched_rule_version_ids == []
    assert result.outputs == {}


def test_gte_amount_matches_threshold() -> None:
    result = apply_rules(
        _transaction(),
        _single_condition_rule({"field": "net_amount", "op": "gte", "value": "10000"}),
    )

    assert result.matched_rule_version_ids == ["rule-version-1"]


def test_gte_amount_below_threshold_does_not_match() -> None:
    result = apply_rules(
        _transaction(),
        _single_condition_rule({"field": "net_amount", "op": "gte", "value": "99999"}),
    )

    assert result.matched_rule_version_ids == []


def test_lte_amount_matches_threshold() -> None:
    result = apply_rules(
        _transaction(),
        _single_condition_rule({"field": "net_amount", "op": "lte", "value": "15000"}),
    )

    assert result.matched_rule_version_ids == ["rule-version-1"]


def test_date_range_gte_matches() -> None:
    """P1-5: 日期范围操作符 date_gte。"""
    result = apply_rules(
        _transaction(),
        _single_condition_rule(
            {"field": "transaction_date", "op": "date_gte", "value": "2026-06-01"}
        ),
    )

    assert result.matched_rule_version_ids == ["rule-version-1"]


def test_date_range_gte_does_not_match() -> None:
    result = apply_rules(
        _transaction(),
        _single_condition_rule(
            {"field": "transaction_date", "op": "date_gte", "value": "2026-07-01"}
        ),
    )

    assert result.matched_rule_version_ids == []


def test_date_range_lte_matches() -> None:
    result = apply_rules(
        _transaction(),
        _single_condition_rule(
            {"field": "transaction_date", "op": "date_lte", "value": "2026-06-30"}
        ),
    )

    assert result.matched_rule_version_ids == ["rule-version-1"]


def test_date_range_lte_does_not_match() -> None:
    result = apply_rules(
        _transaction(),
        _single_condition_rule(
            {"field": "transaction_date", "op": "date_lte", "value": "2026-05-01"}
        ),
    )

    assert result.matched_rule_version_ids == []
