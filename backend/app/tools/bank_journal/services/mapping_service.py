from decimal import Decimal
from typing import Any

from app.tools.bank_journal.domain.conditions import evaluate_leaf
from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def _to_json_safe(value: Any) -> Any:
    """将域类型(Decimal 等)转换为 JSON 可序列化类型。"""
    if isinstance(value, Decimal):
        return str(value)
    return value


def apply_mappings(
    transaction: StandardBankTransaction,
    mappings: list[dict[str, Any]],
    rule_outputs: dict[str, Any],
) -> dict[str, Any]:
    ctx = EvaluationContext.from_transaction(transaction)
    mapped_values: dict[str, Any] = {}

    for mapping in mappings:
        target = mapping["target"]
        mapping_type = mapping.get("type")

        if mapping_type == "field":
            source = mapping.get("source")
            if not isinstance(source, str) or not ctx.has(source):
                raise ValueError(f"Unknown field mapping source for target {target}: {source}")
            value = _to_json_safe(ctx.get(source))
        elif mapping_type == "fixed":
            value = mapping.get("value")
        elif mapping_type == "rule_output":
            value = rule_outputs.get(mapping.get("source"))
        elif mapping_type == "concat":
            separator = mapping.get("separator", "")
            parts = []
            for source in mapping.get("sources", []):
                if not isinstance(source, str) or not ctx.has(source):
                    raise ValueError(
                        f"Unknown concat mapping source for target {target}: {source}"
                    )
                source_value = ctx.get(source)
                if source_value is not None and source_value != "":
                    parts.append(str(source_value))
            value = separator.join(parts)
        elif mapping_type == "conditional":
            condition = mapping.get("condition", {})
            value = (
                mapping.get("then_value")
                if evaluate_leaf(condition, ctx)
                else mapping.get("else_value")
            )
        elif mapping_type == "manual":
            value = None
        else:
            raise ValueError(f"Unsupported mapping type: {mapping_type}")

        mapped_values[target] = value

    return mapped_values
