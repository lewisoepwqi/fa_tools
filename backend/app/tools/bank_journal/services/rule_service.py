from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.tools.bank_journal.enums import ExceptionCode
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


@dataclass
class RuleApplicationResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    matched_rule_version_ids: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    exceptions: list[ExceptionCode] = field(default_factory=list)
    conflicts: dict[str, list[Any]] = field(default_factory=dict)
    all_matched_rules_allow_auto_confirm: bool = False


def apply_rules(
    transaction: StandardBankTransaction,
    rules: list[dict[str, Any]],
) -> RuleApplicationResult:
    result = RuleApplicationResult(all_matched_rules_allow_auto_confirm=False)
    matched_auto_flags: list[bool] = []
    for rule in sorted(rules, key=lambda item: item["priority"]):
        if not _matches(transaction, rule["conditions"]):
            continue
        result.matched_rule_version_ids.append(rule["version_id"])
        matched_auto_flags.append(bool(rule.get("allow_auto_confirm", False)))
        for action in rule["actions"]:
            field_name = action["field"]
            value = action["value"]
            if field_name in result.outputs and result.outputs[field_name] != value:
                values = result.conflicts.setdefault(field_name, [result.outputs[field_name]])
                if value not in values:
                    values.append(value)
                if ExceptionCode.RULE_CONFLICT not in result.exceptions:
                    result.exceptions.append(ExceptionCode.RULE_CONFLICT)
            else:
                result.outputs[field_name] = value
            result.trace.append(
                {
                    "rule_id": rule["id"],
                    "rule_version_id": rule["version_id"],
                    "field": field_name,
                    "value": value,
                }
            )
    result.all_matched_rules_allow_auto_confirm = bool(matched_auto_flags) and all(
        matched_auto_flags
    )
    return result


def _matches(transaction: StandardBankTransaction, conditions: dict[str, Any]) -> bool:
    values = transaction.model_dump()
    return all(_match_condition(values, condition) for condition in conditions.get("all", []))


def _match_condition(values: dict[str, Any], condition: dict[str, Any]) -> bool:
    actual = values.get(condition["field"])
    expected = condition.get("value")
    op = condition["op"]
    if hasattr(actual, "value"):
        actual = actual.value
    if op == "eq":
        return actual == expected
    if op == "contains":
        return expected in str(actual or "")
    if op == "contains_any":
        return any(item in str(actual or "") for item in expected)
    if op == "not_contains":
        return expected not in str(actual or "")
    if op in ("gte", "lte"):
        # 金额区间：缺失/不可解析字段视为不匹配，而非崩溃。
        actual_dec = _decimal_or_none(actual)
        expected_dec = _decimal_or_none(expected)
        if actual_dec is None or expected_dec is None:
            return False
        return actual_dec >= expected_dec if op == "gte" else actual_dec <= expected_dec
    if op in ("date_gte", "date_lte"):
        # 日期范围：按 ISO 日期串比较，缺失/不可解析视为不匹配。
        actual_date = _date_or_none(actual)
        expected_date = _date_or_none(expected)
        if actual_date is None or expected_date is None:
            return False
        return (
            actual_date >= expected_date if op == "date_gte" else actual_date <= expected_date
        )
    raise ValueError(f"Unsupported rule operator: {op}")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    try:
        return Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return None


def _date_or_none(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
