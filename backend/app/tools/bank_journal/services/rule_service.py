from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.tools.bank_journal.domain.conditions import evaluate
from app.tools.bank_journal.domain.fields import EvaluationContext
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
            value = action.get("value")
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
    ctx = EvaluationContext.from_transaction(transaction)
    return evaluate(conditions, ctx)
