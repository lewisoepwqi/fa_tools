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
    ConversionRunListItemResponse,
    ConversionRunResponse,
    ConversionRunSummary,
    JournalPreviewRowData,
)
from app.schemas.standard import StandardBankTransaction
from app.services.mapping_service import apply_mappings
from app.services.parser_service import BankTemplateParseConfig, parse_bank_rows
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
        bank_template_version_id=payload.bank_template_version_id,
        company_journal_template_version_id=payload.company_journal_template_version_id,
        mapping_profile_version_id=payload.mapping_profile_version_id,
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
    parse_failed_count = 0
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
        parsed_rows = parse_bank_rows(file_path, parse_config)

        db.add(
            ConversionRunFile(
                id=str(uuid4()),
                conversion_run_id=run.id,
                source_file_id=source_file_id,
                status="parsed",
                row_count=len(parsed_rows),
            )
        )

        for parsed in parsed_rows:
            if parsed.transaction is None:
                # P1-1: 解析失败行——不构造 bank_transaction（无标准化数据），
                # 直接产出 PARSE_FAILED 预览行，保留原始行快照供人工修正。
                preview_id = str(uuid4())
                exception_codes = list(parsed.parse_errors)
                db.add(
                    JournalPreviewRow(
                        id=preview_id,
                        conversion_run_id=run.id,
                        bank_transaction_id=None,
                        row_index=row_index,
                        output_values_json={
                            "_parse_error": parsed.error_message,
                            "_source_row_index": parsed.source_row_index,
                            "_source_sheet_name": parsed.source_sheet_name,
                            "_raw_row": parsed.raw_row,
                        },
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes_json=[code.value for code in exception_codes],
                        matched_rule_versions_json=[],
                        rule_trace_json=[],
                    )
                )
                preview_rows.append(
                    JournalPreviewRowData(
                        id=preview_id,
                        row_index=row_index,
                        output_values={
                            "_parse_error": parsed.error_message,
                            "_source_row_index": parsed.source_row_index,
                            "_source_sheet_name": parsed.source_sheet_name,
                        },
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes=exception_codes,
                        matched_rule_version_ids=[],
                        rule_trace=[],
                    )
                )
                parse_failed_count += 1
                row_index += 1
                continue

            transaction = parsed.transaction
            bank_tx = _build_bank_transaction(run.id, transaction)
            db.add(bank_tx)

            preview = build_preview_row(
                transaction,
                payload.mappings,
                payload.rules,
                payload.required_columns,
                row_index,
            )
            preview_id = str(uuid4())
            db.add(
                JournalPreviewRow(
                    id=preview_id,
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
            preview_rows.append(preview.model_copy(update={"id": preview_id}))
            row_index += 1

    run.summary_json = {
        "total_rows": len(preview_rows),
        "parse_failed_rows": parse_failed_count,
    }
    db.commit()

    return ConversionRunResponse(
        id=run.id,
        status=run.status,
        summary=ConversionRunSummary(total_rows=len(preview_rows)),
        preview_rows=preview_rows,
        company_id=run.company_id,
        bank_account_id=run.bank_account_id,
        created_at=run.created_at,
        completed_at=run.completed_at,
        bank_template_version_id=run.bank_template_version_id,
        company_journal_template_version_id=run.company_journal_template_version_id,
        mapping_profile_version_id=run.mapping_profile_version_id,
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


def _summary_from_json(raw: dict[str, object] | None) -> ConversionRunSummary:
    return ConversionRunSummary(
        total_rows=int(raw.get("total_rows", 0)) if raw else 0,
        parse_failed_rows=int(raw.get("parse_failed_rows", 0)) if raw else 0,
    )


def list_conversion_runs(
    db: Session, company_id: str | None = None
) -> list[ConversionRunListItemResponse]:
    """返回所有批次（不含预览行），按创建时间倒序。"""
    query = db.query(ConversionRun)
    if company_id is not None:
        query = query.filter(ConversionRun.company_id == company_id)
    runs = query.order_by(ConversionRun.created_at.desc()).all()
    return [
        ConversionRunListItemResponse(
            id=run.id,
            company_id=run.company_id,
            bank_account_id=run.bank_account_id,
            status=run.status,
            summary=_summary_from_json(run.summary_json),
            created_at=run.created_at,
            completed_at=run.completed_at,
            bank_template_version_id=run.bank_template_version_id,
            company_journal_template_version_id=run.company_journal_template_version_id,
            mapping_profile_version_id=run.mapping_profile_version_id,
        )
        for run in runs
    ]


def _preview_row_to_data(row: JournalPreviewRow) -> JournalPreviewRowData:
    return JournalPreviewRowData(
        id=row.id,
        row_index=row.row_index,
        output_values=row.output_values_json or {},
        status=PreviewStatus(row.status),
        exception_codes=[ExceptionCode(code) for code in (row.exception_codes_json or [])],
        matched_rule_version_ids=row.matched_rule_versions_json or [],
        rule_trace=_rule_trace_to_list(row.rule_trace_json),
    )


def _rule_trace_to_list(raw: object) -> list[dict[str, Any]]:
    # 模型列 rule_trace_json 在 schema 里是 list[dict]；兼容历史 dict 写入。
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def get_conversion_run(db: Session, run_id: str) -> ConversionRunResponse:
    """按 id 加载批次详情（含预览行）。不存在则 404。"""
    run = db.query(ConversionRun).filter(ConversionRun.id == run_id).first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion run not found: {run_id}",
        )
    rows = (
        db.query(JournalPreviewRow)
        .filter(JournalPreviewRow.conversion_run_id == run_id)
        .order_by(JournalPreviewRow.row_index.asc())
        .all()
    )
    return ConversionRunResponse(
        id=run.id,
        status=run.status,
        summary=_summary_from_json(run.summary_json),
        preview_rows=[_preview_row_to_data(row) for row in rows],
        company_id=run.company_id,
        bank_account_id=run.bank_account_id,
        created_at=run.created_at,
        completed_at=run.completed_at,
        bank_template_version_id=run.bank_template_version_id,
        company_journal_template_version_id=run.company_journal_template_version_id,
        mapping_profile_version_id=run.mapping_profile_version_id,
    )
