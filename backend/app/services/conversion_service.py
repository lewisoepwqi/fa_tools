from __future__ import annotations

from typing import Any

from app.core.enums import ExceptionCode, PreviewStatus
from app.schemas.conversion import JournalPreviewRowData
from app.schemas.standard import StandardBankTransaction
from app.services.mapping_service import apply_mappings
from app.services.rule_service import apply_rules


def build_preview_row(
    transaction: StandardBankTransaction,
    mappings: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    required_columns: list[str],
    row_index: int,
) -> JournalPreviewRowData:
    rule_result = apply_rules(transaction, rules)
    output_values = apply_mappings(transaction, mappings, rule_result.outputs)
    exceptions = list(rule_result.exceptions)
    missing_required = [
        column for column in required_columns if output_values.get(column) in (None, "")
    ]
    if missing_required and ExceptionCode.MISSING_REQUIRED_FIELD not in exceptions:
        exceptions.append(ExceptionCode.MISSING_REQUIRED_FIELD)
    if not rule_result.matched_rule_version_ids and ExceptionCode.NO_RULE_MATCH not in exceptions:
        exceptions.append(ExceptionCode.NO_RULE_MATCH)
    status = _preview_status(exceptions, rule_result.all_matched_rules_allow_auto_confirm)
    return JournalPreviewRowData(
        row_index=row_index,
        output_values=output_values,
        status=status,
        exception_codes=exceptions,
        matched_rule_version_ids=rule_result.matched_rule_version_ids,
        rule_trace=rule_result.trace,
    )


def _preview_status(
    exceptions: list[ExceptionCode],
    all_matched_rules_allow_auto_confirm: bool,
) -> PreviewStatus:
    if ExceptionCode.RULE_CONFLICT in exceptions:
        return PreviewStatus.CONFLICT
    if ExceptionCode.MISSING_REQUIRED_FIELD in exceptions:
        return PreviewStatus.NEEDS_CONFIRMATION
    if ExceptionCode.NO_RULE_MATCH in exceptions:
        return PreviewStatus.NEEDS_CONFIRMATION
    if all_matched_rules_allow_auto_confirm:
        return PreviewStatus.AUTO_CONFIRMED
    return PreviewStatus.NEEDS_CONFIRMATION
