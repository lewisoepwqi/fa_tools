from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import AmountMode, ExceptionCode, PreviewStatus
from app.models.conversion import (
    BankTransaction,
    ConversionRun,
    ConversionRunFile,
    ConversionRunRuleVersion,
    JournalPreviewRow,
)
from app.models.file import SourceFile
from app.schemas.conversion import (
    ConversionRunCreate,
    ConversionRunResponse,
    ConversionRunSummary,
    JournalPreviewRowData,
)
from app.schemas.standard import StandardBankTransaction
from app.services.mapping_service import apply_mappings
from app.services.parser_service import BankTemplateParseConfig, parse_bank_statement
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


def run_conversion(
    db: Session, payload: ConversionRunCreate, upload_dir: Path
) -> ConversionRunResponse:
    run = ConversionRun(
        id=str(uuid4()),
        company_id=payload.company_id,
        bank_account_id=payload.bank_account_id,
        status="completed",
        completed_at=datetime.now(UTC),
        summary_json={},
    )
    db.add(run)

    for rule in payload.rules:
        db.add(
            ConversionRunRuleVersion(
                id=str(uuid4()),
                conversion_run_id=run.id,
                rule_version_id=rule["version_id"],
            )
        )

    config = payload.bank_parse_config
    amount_mode = AmountMode(config.amount_mode)

    preview_rows: list[JournalPreviewRowData] = []
    row_index = 1
    for source_file_id in payload.source_file_ids:
        source = db.query(SourceFile).filter(SourceFile.id == source_file_id).first()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source file not found: {source_file_id}",
            )

        file_path = upload_dir / source.storage_key
        parse_config = BankTemplateParseConfig(
            bank_account_id=payload.bank_account_id,
            source_file_id=source_file_id,
            file_type=source.file_type,
            sheet_name=config.sheet_name,
            header_row_index=config.header_row_index,
            data_start_row_index=config.data_start_row_index,
            field_aliases=config.field_aliases,
            amount_mode=amount_mode,
            amount_config=config.amount_config,
            date_formats=config.date_formats,
        )
        transactions = parse_bank_statement(file_path, parse_config)

        db.add(
            ConversionRunFile(
                id=str(uuid4()),
                conversion_run_id=run.id,
                source_file_id=source_file_id,
                status="parsed",
                row_count=len(transactions),
            )
        )

        for transaction in transactions:
            bank_tx = _build_bank_transaction(run.id, transaction)
            db.add(bank_tx)

            preview = build_preview_row(
                transaction,
                payload.mappings,
                payload.rules,
                payload.required_columns,
                row_index,
            )
            db.add(
                JournalPreviewRow(
                    id=str(uuid4()),
                    conversion_run_id=run.id,
                    bank_transaction_id=bank_tx.id,
                    row_index=row_index,
                    output_values_json=preview.output_values,
                    status=preview.status,
                    exception_codes_json=preview.exception_codes,
                    matched_rule_versions_json=preview.matched_rule_version_ids,
                    rule_trace_json=preview.rule_trace,
                )
            )
            preview_rows.append(preview)
            row_index += 1

    run.summary_json = {"total_rows": len(preview_rows)}
    db.commit()

    return ConversionRunResponse(
        id=run.id,
        status=run.status,
        summary=ConversionRunSummary(total_rows=len(preview_rows)),
        preview_rows=preview_rows,
    )


def _build_bank_transaction(run_id: str, txn: StandardBankTransaction) -> BankTransaction:
    return BankTransaction(
        id=str(uuid4()),
        conversion_run_id=run_id,
        source_file_id=txn.source_file_id,
        source_sheet_name=txn.source_sheet_name,
        source_row_index=txn.source_row_index,
        transaction_date=date.fromisoformat(txn.transaction_date),
        posting_date=date.fromisoformat(txn.posting_date) if txn.posting_date else None,
        bank_account_id=txn.bank_account_id,
        currency=txn.currency,
        direction=txn.direction.value,
        debit_amount=txn.debit_amount,
        credit_amount=txn.credit_amount,
        net_amount=txn.net_amount,
        balance=txn.balance,
        counterparty_name=txn.counterparty_name,
        counterparty_account_no_encrypted=txn.counterparty_account_no,
        counterparty_bank_name=txn.counterparty_bank_name,
        summary=txn.summary,
        purpose=txn.purpose,
        transaction_type=txn.transaction_type,
        bank_transaction_id=txn.bank_transaction_id,
        receipt_no=txn.receipt_no,
        raw_row_json=txn.raw_row,
    )
