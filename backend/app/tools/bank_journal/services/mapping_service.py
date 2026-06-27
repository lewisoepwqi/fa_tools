from typing import Any

from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.rule_service import _match_condition


def apply_mappings(
    transaction: StandardBankTransaction,
    mappings: list[dict[str, Any]],
    rule_outputs: dict[str, Any],
) -> dict[str, Any]:
    transaction_data = transaction.model_dump(mode="json")
    mapped_values: dict[str, Any] = {}

    for mapping in mappings:
        target = mapping["target"]
        mapping_type = mapping.get("type")

        if mapping_type == "field":
            source = mapping.get("source")
            if not isinstance(source, str) or source not in transaction_data:
                raise ValueError(f"Unknown field mapping source for target {target}: {source}")
            value = transaction_data[source]
        elif mapping_type == "fixed":
            value = mapping.get("value")
        elif mapping_type == "rule_output":
            value = rule_outputs.get(mapping.get("source"))
        elif mapping_type == "concat":
            separator = mapping.get("separator", "")
            values = []
            for source in mapping.get("sources", []):
                if not isinstance(source, str) or source not in transaction_data:
                    raise ValueError(f"Unknown concat mapping source for target {target}: {source}")
                source_value = transaction_data[source]
                if source_value is not None and source_value != "":
                    values.append(str(source_value))
            value = separator.join(values)
        elif mapping_type == "conditional":
            condition = mapping.get("condition", {})
            value = (
                mapping.get("then_value")
                if _match_condition(transaction_data, condition)
                else mapping.get("else_value")
            )
        elif mapping_type == "manual":
            value = None
        else:
            raise ValueError(f"Unsupported mapping type: {mapping_type}")

        mapped_values[target] = value

    return mapped_values
