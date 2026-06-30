from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.file import SourceFile
from app.tools.bank_journal.domain.balance import check_balance_continuity
from app.tools.bank_journal.domain.dedup import mark_duplicates, row_hash
from app.tools.bank_journal.enums import AmountMode, ExceptionCode, PreviewStatus, RunStatus
from app.tools.bank_journal.models.conversion import (
    BankTransaction,
    ConversionRun,
    ConversionRunFile,
    ConversionRunRuleVersion,
    JournalPreviewRow,
)
from app.tools.bank_journal.models.mapping import MappingProfile, MappingProfileVersion
from app.tools.bank_journal.models.rule import Rule, RuleVersion
from app.tools.bank_journal.models.template import (
    BankTemplate,
    BankTemplateVersion,
    CompanyJournalTemplate,
    CompanyJournalTemplateVersion,
)
from app.tools.bank_journal.schemas.conversion import (
    BankParseConfig,
    ConversionRunCreate,
    ConversionRunFromConfigCreate,
    ConversionRunListItemResponse,
    ConversionRunResponse,
    ConversionRunSummary,
    DryRunCreate,
    DryRunResponse,
    JournalPreviewRowData,
)
from app.tools.bank_journal.schemas.pagination import Page
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.custom_field_service import load_custom_field_defs
from app.tools.bank_journal.services.mapping_service import apply_mappings
from app.tools.bank_journal.services.parser_service import (
    BankTemplateParseConfig,
    CustomFieldDef,
    parse_bank_rows,
)
from app.tools.bank_journal.services.rule_service import apply_rules

# 携带任意一个此集合内的异常码时，AUTO_CONFIRMED 必须被降级为 NEEDS_CONFIRMATION。
# 这些码全部由"事后处理"步骤（warnings 合并、去重、余额连续性）写入，
# build_preview_row 在设定状态时尚未持有这些信息，故需在所有后处理完成后统一降级。
_MUST_CONFIRM_CODES: frozenset[ExceptionCode] = frozenset({
    ExceptionCode.AMOUNT_DIRECTION_MISMATCH,
    ExceptionCode.DUPLICATE_IN_BATCH,
    ExceptionCode.DUPLICATE_HISTORY,
    ExceptionCode.BALANCE_DISCONTINUITY,
})


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


def create_pending_run(db: Session, payload: ConversionRunCreate) -> ConversionRun:
    """建立 PENDING 状态的转换批次，关联规则版本快照，flush 但不 commit，返回 run。"""
    rules = [r.model_dump(by_alias=True, exclude_none=True) for r in payload.rules]

    run = ConversionRun(
        id=str(uuid4()),
        company_id=payload.company_id,
        bank_account_id=payload.bank_account_id,
        status=RunStatus.PENDING,
        summary_json={},
        bank_template_version_id=payload.bank_template_version_id,
        company_journal_template_version_id=payload.company_journal_template_version_id,
        mapping_profile_version_id=payload.mapping_profile_version_id,
    )
    db.add(run)
    # 先将 conversion_runs 落库，确保后续子行（bank_transactions 等）的外键引用有效。
    # SQLAlchemy 无 relationship() 时不保证 flush 顺序；显式 flush 消除竞态。
    db.flush()

    for rule in rules:
        db.add(
            ConversionRunRuleVersion(
                id=str(uuid4()),
                conversion_run_id=run.id,
                rule_version_id=rule["version_id"],
            )
        )

    return run


def _parse_and_build_rows(
    db: Session,
    run: ConversionRun,
    payload: ConversionRunCreate,
    upload_dir: Path,
) -> tuple[list[JournalPreviewRowData], int]:
    """解析所有源文件 + 构建预览行 + 去重 + 降级，写入 session（未提交）。

    返回 (preview_rows, parse_failed_count)。
    此函数是模块级函数，方便测试通过 monkeypatch 注入失败场景。
    """
    # 契约模型 → dict，喂给现有 domain/service。
    # by_alias=True: 还原 not_→not（ConditionIn.not_ alias="not"）。
    # exclude_none=True: 避免空字段（all/any/not/field=None）干扰 evaluate() 的键存在检测。
    mappings = [m.model_dump(by_alias=True, exclude_none=True) for m in payload.mappings]
    rules = [r.model_dump(by_alias=True, exclude_none=True) for r in payload.rules]

    config = payload.bank_parse_config
    amount_mode = AmountMode(config.amount_mode)

    # 加载公司级扩展字段定义（识别 + 填充 + 落库槽位反查复用）
    custom_defs = load_custom_field_defs(db, payload.company_id)

    # 从银行模板版本提取去重关键字段（无则用默认值）。
    key_fields: list[str] | None = None
    if payload.bank_template_version_id:
        tv = db.get(BankTemplateVersion, payload.bank_template_version_id)
        if tv is not None and tv.unique_key_config_json:
            kf = list(tv.unique_key_config_json.get("fields") or [])
            if kf:
                key_fields = kf

    # 本批写入前一次性查出该公司历史已提交批次的 row_hash 集合（本批尚未落库）。
    history: set[str] = {
        h
        for (h,) in db.query(BankTransaction.row_hash)
        .join(ConversionRun, BankTransaction.conversion_run_id == ConversionRun.id)
        .filter(
            ConversionRun.company_id == payload.company_id,
            BankTransaction.row_hash.isnot(None),
        )
    }

    preview_rows: list[JournalPreviewRowData] = []
    # 成功行追踪列表，用于批末去重标注：(bank_tx, preview_db_row, preview_rows 下标)。
    success_entries: list[tuple[BankTransaction, JournalPreviewRow, int]] = []
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
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source file missing on disk: {source_file_id}",
            )
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
            custom_fields=custom_defs,
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

        # 本文件的成功行追踪（余额连续性校验按文件隔离）。
        file_success_entries: list[tuple[BankTransaction, JournalPreviewRow, int]] = []

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
            try:
                bank_tx = _build_bank_transaction(
                    run.id, transaction, _slot_map_for(custom_defs)
                )
                bank_tx.row_hash = row_hash(transaction, key_fields)
                preview = build_preview_row(
                    transaction,
                    mappings,
                    rules,
                    payload.required_columns,
                    row_index,
                )
                db.add(bank_tx)  # stage only after both succeed → no orphan if preview throws
                for code in parsed.warnings:
                    if code not in preview.exception_codes:
                        preview.exception_codes.append(code)
            except Exception as exc:  # noqa: BLE001  单行隔离:任何处理错误降级为失败行,不中断整批
                preview_id = str(uuid4())
                db.add(
                    JournalPreviewRow(
                        id=preview_id,
                        conversion_run_id=run.id,
                        bank_transaction_id=None,
                        row_index=row_index,
                        output_values_json={"_processing_error": str(exc)},
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes_json=[ExceptionCode.INVALID_AMOUNT.value],
                        matched_rule_versions_json=[],
                        rule_trace_json=[],
                    )
                )
                preview_rows.append(
                    JournalPreviewRowData(
                        id=preview_id,
                        row_index=row_index,
                        output_values={"_processing_error": str(exc)},
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes=[ExceptionCode.INVALID_AMOUNT],
                        matched_rule_version_ids=[],
                        rule_trace=[],
                    )
                )
                parse_failed_count += 1
                row_index += 1
                continue
            preview_id = str(uuid4())
            preview_db_row = JournalPreviewRow(
                id=preview_id,
                conversion_run_id=run.id,
                bank_transaction_id=bank_tx.id,
                row_index=row_index,
                output_values_json=preview.output_values,
                status=preview.status,
                exception_codes_json=[c.value for c in preview.exception_codes],
                matched_rule_versions_json=preview.matched_rule_version_ids,
                rule_trace_json=preview.rule_trace,
            )
            db.add(preview_db_row)
            preview_data = preview.model_copy(update={"id": preview_id})
            preview_rows.append(preview_data)
            pr_idx = len(preview_rows) - 1
            success_entries.append((bank_tx, preview_db_row, pr_idx))
            file_success_entries.append((bank_tx, preview_db_row, pr_idx))
            row_index += 1

        # 余额连续性校验（按本文件 source_row_index 升序，隔离于其他文件）。
        if file_success_entries:
            file_success_entries.sort(key=lambda e: e[0].source_row_index)
            balance_rows = [(bt.balance, bt.net_amount) for bt, _, _ in file_success_entries]
            flags = check_balance_continuity(balance_rows)
            for (_, preview_db_row, pr_idx), flag in zip(
                file_success_entries, flags, strict=True
            ):
                if flag:
                    ec_str = ExceptionCode.BALANCE_DISCONTINUITY.value
                    existing_json = list(preview_db_row.exception_codes_json or [])
                    if ec_str not in existing_json:
                        existing_json.append(ec_str)
                        preview_db_row.exception_codes_json = existing_json
                    pdata = preview_rows[pr_idx]
                    if ExceptionCode.BALANCE_DISCONTINUITY not in pdata.exception_codes:
                        pdata.exception_codes.append(ExceptionCode.BALANCE_DISCONTINUITY)

    # 批末去重标注：批内重复 + 历史重复。
    if success_entries:
        batch_hashes = [bt.row_hash for bt, _, _ in success_entries]
        dup_codes = mark_duplicates(batch_hashes, history)  # type: ignore[arg-type]
        for (_, preview_db_row, pr_idx), code in zip(success_entries, dup_codes, strict=True):
            if code is not None:
                ec_str = code.value
                existing_json = list(preview_db_row.exception_codes_json or [])
                if ec_str not in existing_json:
                    existing_json.append(ec_str)
                    preview_db_row.exception_codes_json = existing_json
                pdata = preview_rows[pr_idx]
                if code not in pdata.exception_codes:
                    pdata.exception_codes.append(code)

    # 最终降级：所有后处理（warnings / 去重 / 余额连续性）完成后，
    # 若 AUTO_CONFIRMED 行持有任意"必须确认"异常码，强制降为 NEEDS_CONFIRMATION。
    # 仅针对 AUTO_CONFIRMED；其他终态（CONFLICT/PARSE_FAILED/MANUALLY_CONFIRMED/IGNORED）不受影响。
    for _, preview_db_row, pr_idx in success_entries:
        pdata = preview_rows[pr_idx]
        if (
            pdata.status == PreviewStatus.AUTO_CONFIRMED
            and _MUST_CONFIRM_CODES.intersection(pdata.exception_codes)
        ):
            pdata.status = PreviewStatus.NEEDS_CONFIRMATION
            preview_db_row.status = PreviewStatus.NEEDS_CONFIRMATION

    return preview_rows, parse_failed_count


def process_conversion_run(
    db: Session,
    run_id: str,
    upload_dir: Path,
    payload: ConversionRunCreate | None = None,
) -> ConversionRunResponse:
    """PROCESSING → try 解析/落库/summary → COMPLETED；异常 → FAILED + error_message，不抛 500。

    payload 为 None 时依赖调用方已 monkeypatch _parse_and_build_rows（测试场景）。
    """
    run = db.get(ConversionRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion run not found: {run_id}",
        )

    run.status = RunStatus.PROCESSING
    db.flush()

    try:
        preview_rows, parse_failed_count = _parse_and_build_rows(db, run, payload, upload_dir)  # type: ignore[arg-type]

        status_counts: Counter[str] = Counter(p.status for p in preview_rows)
        run.summary_json = {
            "total_rows": len(preview_rows),
            "parse_failed_rows": parse_failed_count,
            "auto_confirmed_rows": status_counts.get(PreviewStatus.AUTO_CONFIRMED, 0),
            "needs_confirmation_rows": status_counts.get(PreviewStatus.NEEDS_CONFIRMATION, 0),
            "conflict_rows": status_counts.get(PreviewStatus.CONFLICT, 0),
        }
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(UTC)
        db.commit()

        # 优先从绑定的日记账模板版本取列定义；无绑定则从本批预览行键并集回退。
        journal_cols = _journal_columns_from_template(
            db, payload.company_journal_template_version_id
        )
        if not journal_cols:
            journal_cols = _journal_columns_from_rows_data(preview_rows)

        return ConversionRunResponse(
            id=run.id,
            status=run.status,
            summary=ConversionRunSummary(
                total_rows=len(preview_rows),
                parse_failed_rows=parse_failed_count,
                auto_confirmed_rows=status_counts.get(PreviewStatus.AUTO_CONFIRMED, 0),
                needs_confirmation_rows=status_counts.get(PreviewStatus.NEEDS_CONFIRMATION, 0),
                conflict_rows=status_counts.get(PreviewStatus.CONFLICT, 0),
            ),
            preview_rows=preview_rows,
            company_id=run.company_id,
            bank_account_id=run.bank_account_id,
            created_at=run.created_at,
            completed_at=run.completed_at,
            bank_template_version_id=run.bank_template_version_id,
            company_journal_template_version_id=run.company_journal_template_version_id,
            mapping_profile_version_id=run.mapping_profile_version_id,
            journal_columns=journal_cols,
        )

    except HTTPException:
        # 用户输入类错误（404 源文件不存在等）：回滚 PROCESSING 状态，直接重抛，不污染 run 状态。
        db.rollback()
        raise
    except Exception as e:  # noqa: BLE001
        # 回滚部分写入的 preview rows / bank_transactions 等。
        # run 记录本身已在上一事务提交，rollback 不影响。
        db.rollback()
        # rollback 后 ORM 对象过期，必须重取 run。
        run = db.get(ConversionRun, run_id)
        run.status = RunStatus.FAILED
        run.error_message = str(e)[:2000]
        db.commit()
        return ConversionRunResponse(
            id=run.id,
            status=RunStatus.FAILED,
            error_message=run.error_message,
            summary=ConversionRunSummary(),
            preview_rows=[],
            company_id=run.company_id,
            bank_account_id=run.bank_account_id,
            created_at=run.created_at,
            completed_at=None,
            bank_template_version_id=run.bank_template_version_id,
            company_journal_template_version_id=run.company_journal_template_version_id,
            mapping_profile_version_id=run.mapping_profile_version_id,
        )


def run_conversion(
    db: Session, payload: ConversionRunCreate, upload_dir: Path
) -> ConversionRunResponse:
    """建立 pending run 后立即处理（同步）；签名与返回类型不变。"""
    run = create_pending_run(db, payload)
    db.commit()
    return process_conversion_run(db, run.id, upload_dir, payload)


# ---------------------------------------------------------------------------
# P0：从已配置的版本化模板/映射/规则驱动转换。
# 解决根因：run_conversion 纯用前端内联参数，用户配置的四个模块与转换链路从未连通。
# 这里把 DB 里的版本化配置查出来，转成 run_conversion 期望的内联形态后复用它执行。
# ---------------------------------------------------------------------------


def run_conversion_from_config(
    db: Session, payload: ConversionRunFromConfigCreate, upload_dir: Path
) -> ConversionRunResponse:
    """用已配置的模板/映射/规则版本驱动一次转换（落库，记录快照版本 ID）。"""
    bank_version = _resolve_bank_template_version(db, payload)
    journal_version = _resolve_journal_template_version(db, payload)
    mapping_version = _resolve_mapping_profile_version(db, payload)
    rule_versions = _resolve_rule_versions(db, payload.rule_ids)

    bank_parse_config = _bank_version_to_parse_config(bank_version)
    mappings = _mapping_version_to_mappings(mapping_version)
    rules = [_rule_version_to_rule_dict(rv) for rv in rule_versions]
    required_columns = (
        list(payload.required_columns)
        if payload.required_columns
        else list(journal_version.required_columns_json or [])
    )

    inline_payload = ConversionRunCreate(
        company_id=payload.company_id,
        bank_account_id=payload.bank_account_id,
        source_file_ids=payload.source_file_ids,
        bank_parse_config=bank_parse_config,
        mappings=mappings,
        rules=rules,
        required_columns=required_columns,
        # 快照本次使用的版本 ID，供导出报告/批次详情溯源。
        bank_template_version_id=bank_version.id,
        company_journal_template_version_id=journal_version.id,
        mapping_profile_version_id=mapping_version.id if mapping_version else None,
    )
    return run_conversion(db, inline_payload, upload_dir)


def dry_run_conversion(
    db: Session, payload: DryRunCreate, upload_dir: Path
) -> DryRunResponse:
    """P3：试跑——用配置 ID 解析文件并计算预览行，但**不落库**（无 ConversionRun/事务）。

    复用与 run_conversion_from_config 相同的配置解析与 parse/preview 逻辑，
    仅省略所有 DB 写入。供向导/详情页在保存配置前即时验证效果。
    """
    bank_version = _resolve_bank_template_version(db, payload)
    mapping_version = _resolve_mapping_profile_version(db, payload)
    rule_versions = _resolve_rule_versions(db, payload.rule_ids)
    amount_mode = AmountMode(bank_version.amount_mode)

    # 通过银行模板反查公司，加载其扩展字段定义（预览/规则/映射要用扩展字段）
    bank_template = (
        db.query(BankTemplate)
        .filter(BankTemplate.id == bank_version.bank_template_id)
        .first()
    )
    custom_defs: list[CustomFieldDef] = []
    if bank_template is not None and bank_template.company_id:
        custom_defs = load_custom_field_defs(db, bank_template.company_id)

    field_aliases = dict(bank_version.field_aliases_json or {})
    amount_config = dict(bank_version.amount_config_json or {})
    date_formats = list(bank_version.date_formats_json or ["%Y-%m-%d"])
    selector = bank_version.sheet_selector_json or {}
    sheet_name = str(selector.get("sheet_name") or "Sheet1")
    header_row_index = (
        bank_version.header_row_index if bank_version.header_row_index is not None else 0
    )
    data_start_row_index = (
        bank_version.data_start_row_index if bank_version.data_start_row_index is not None else 1
    )
    mappings = _mapping_version_to_mappings(mapping_version)
    rules = [_rule_version_to_rule_dict(rv) for rv in rule_versions]

    preview_rows: list[JournalPreviewRowData] = []
    row_index = 1
    parse_failed_count = 0
    limit = max(payload.limit, 1)

    for source_file_id in payload.source_file_ids:
        if len(preview_rows) >= limit:
            break
        source = db.query(SourceFile).filter(SourceFile.id == source_file_id).first()
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source file not found: {source_file_id}",
            )
        file_path = upload_dir / source.storage_key
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source file missing on disk: {source_file_id}",
            )
        parse_config = BankTemplateParseConfig(
            bank_account_id=payload.bank_account_id,
            source_file_id=source_file_id,
            file_type=source.file_type,
            sheet_name=sheet_name,
            header_row_index=header_row_index,
            data_start_row_index=data_start_row_index,
            field_aliases=field_aliases,
            amount_mode=amount_mode,
            amount_config=amount_config,
            date_formats=date_formats,
            custom_fields=custom_defs,
        )
        for parsed in parse_bank_rows(file_path, parse_config):
            if len(preview_rows) >= limit:
                break
            if parsed.transaction is None:
                preview_rows.append(
                    JournalPreviewRowData(
                        row_index=row_index,
                        output_values={
                            "_parse_error": parsed.error_message,
                            "_source_row_index": parsed.source_row_index,
                        },
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes=list(parsed.parse_errors),
                        matched_rule_version_ids=[],
                        rule_trace=[],
                    )
                )
                parse_failed_count += 1
                row_index += 1
                continue
            preview = build_preview_row(
                parsed.transaction,
                mappings,
                rules,
                [],
                row_index,
            )
            for code in parsed.warnings:
                if code not in preview.exception_codes:
                    preview.exception_codes.append(code)
            # 降级：warnings 合并完成后，AUTO_CONFIRMED 行若持有"必须确认"异常码则降级。
            if (
                preview.status == PreviewStatus.AUTO_CONFIRMED
                and _MUST_CONFIRM_CODES.intersection(preview.exception_codes)
            ):
                preview.status = PreviewStatus.NEEDS_CONFIRMATION
            preview_rows.append(preview)
            row_index += 1

    dry_status_counts: Counter[str] = Counter(p.status for p in preview_rows)
    return DryRunResponse(
        summary=ConversionRunSummary(
            total_rows=len(preview_rows),
            parse_failed_rows=parse_failed_count,
            auto_confirmed_rows=dry_status_counts.get(PreviewStatus.AUTO_CONFIRMED, 0),
            needs_confirmation_rows=dry_status_counts.get(PreviewStatus.NEEDS_CONFIRMATION, 0),
            conflict_rows=dry_status_counts.get(PreviewStatus.CONFLICT, 0),
        ),
        preview_rows=preview_rows,
    )


def _resolve_bank_template_version(
    db: Session, payload: ConversionRunFromConfigCreate
) -> BankTemplateVersion:
    if payload.bank_template_version_id:
        v = db.get(BankTemplateVersion, payload.bank_template_version_id)
    elif payload.bank_template_id:
        _ensure_parent_active(db, BankTemplate, payload.bank_template_id, "bank_template")
        v = _latest_version(
            db, BankTemplateVersion, "bank_template_id", payload.bank_template_id
        )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "bank_template_version_id or bank_template_id required",
        )
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bank template version not found")
    return v


def _resolve_journal_template_version(
    db: Session, payload: ConversionRunFromConfigCreate
) -> CompanyJournalTemplateVersion:
    if payload.company_journal_template_version_id:
        v = db.get(CompanyJournalTemplateVersion, payload.company_journal_template_version_id)
    elif payload.company_journal_template_id:
        _ensure_parent_active(
            db, CompanyJournalTemplate, payload.company_journal_template_id, "journal_template"
        )
        v = _latest_version(
            db,
            CompanyJournalTemplateVersion,
            "company_journal_template_id",
            payload.company_journal_template_id,
        )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "company_journal_template_version_id or company_journal_template_id required",
        )
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Journal template version not found")
    return v


def _resolve_mapping_profile_version(
    db: Session, payload: ConversionRunFromConfigCreate
) -> MappingProfileVersion | None:
    if payload.mapping_profile_version_id:
        v = db.get(MappingProfileVersion, payload.mapping_profile_version_id)
    elif payload.mapping_profile_id:
        _ensure_parent_active(
            db, MappingProfile, payload.mapping_profile_id, "mapping_profile"
        )
        v = _latest_version(
            db, MappingProfileVersion, "mapping_profile_id", payload.mapping_profile_id
        )
    else:
        return None
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mapping profile version not found")
    return v


def _resolve_rule_versions(db: Session, rule_ids: list[str]) -> list[RuleVersion]:
    out: list[RuleVersion] = []
    for rule_id in rule_ids:
        _ensure_parent_active(db, Rule, rule_id, "rule")
        v = _latest_version(db, RuleVersion, "rule_id", rule_id)
        if v is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Rule version not found: {rule_id}")
        out.append(v)
    return out


def _latest_version(db: Session, model: type, fk_col: str, parent_id: str):
    """取某父实体的最新版本（version_no 倒序首条）。"""
    column = getattr(model, fk_col)
    return (
        db.query(model)
        .filter(column == parent_id)
        .order_by(model.version_no.desc())
        .first()
    )


def _ensure_parent_active(db: Session, model: type, parent_id: str, label: str) -> None:
    parent = db.get(model, parent_id)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found: {parent_id}")
    # 停用的配置不应被新批次引用（保守，符合 PRD 版本化/启用约定）。
    if getattr(parent, "status", "active") != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} is not active: {parent_id}")


def _bank_version_to_parse_config(v: BankTemplateVersion) -> BankParseConfig:
    """模板版本字段（带 _json 后缀）→ parse 期望的 BankParseConfig（无后缀）。

    注意 sheet_name 取自 sheet_selector_json.sheet_name（兼容缺失时回落 "Sheet1"）。
    """
    selector = v.sheet_selector_json or {}
    return BankParseConfig(
        file_type=v.file_type,
        sheet_name=str(selector.get("sheet_name") or "Sheet1"),
        header_row_index=v.header_row_index if v.header_row_index is not None else 0,
        data_start_row_index=(
            v.data_start_row_index if v.data_start_row_index is not None else 1
        ),
        field_aliases=dict(v.field_aliases_json or {}),
        amount_mode=v.amount_mode,
        amount_config=dict(v.amount_config_json or {}),
        date_formats=list(v.date_formats_json or ["%Y-%m-%d"]),
    )


def _mapping_version_to_mappings(
    v: MappingProfileVersion | None,
) -> list[dict[str, Any]]:
    """mappings_json → apply_mappings 期望的 list[{target,type,...}]。

    支持两种存储格式（P1 富模型 + 向后兼容）：
    - 扁平 {目标列:标准字段}：默认 type='field'。
    - mappings_json['_advanced']：富模型数组，含 type/source/value/sources 等。
    """
    if v is None or not v.mappings_json:
        return []
    out: list[dict[str, Any]] = []
    for target, source in v.mappings_json.items():
        if target == "_advanced":
            continue
        out.append({"target": target, "type": "field", "source": source})
    advanced = v.mappings_json.get("_advanced") or []
    if isinstance(advanced, list):
        for item in advanced:
            if isinstance(item, dict) and item.get("target"):
                out.append(dict(item))
    return out


def _rule_version_to_rule_dict(v: RuleVersion) -> dict[str, Any]:
    """RuleVersion（conditions_json/actions_json.set）→ apply_rules 期望的 rule dict。

    关键差异：存储的 actions_json 是 {set:{field:value}}，而 apply_rules 要求
    actions 是 list[{field,value}]；conditions 两者都是 {all:[...]} 直接透传。
    """
    actions_obj = v.actions_json or {}
    actions_list = [
        {"field": field, "value": value} for field, value in (actions_obj.get("set") or {}).items()
    ]
    return {
        "id": v.rule_id,
        "version_id": v.id,
        "priority": v.priority if v.priority is not None else 0,
        "conditions": v.conditions_json or {"all": []},
        "actions": actions_list,
        "allow_auto_confirm": v.allow_auto_confirm,
    }


def _slot_map_for(defs: list[CustomFieldDef]) -> dict[str, CustomFieldDef]:
    """field_key → CustomFieldDef，供 _build_bank_transaction 反查落库槽位。"""
    return {d.field_key: d for d in defs}


def _build_bank_transaction(
    run_id: str, txn: StandardBankTransaction, slot_map: dict[str, CustomFieldDef] | None = None
) -> BankTransaction:
    kwargs: dict[str, Any] = dict(
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
    # 把 extra_fields 按 field_key → slot_key 反查,按类型转换后写入对应预分配列。
    if slot_map and txn.extra_fields:
        for field_key, value in txn.extra_fields.items():
            cf = slot_map.get(field_key)
            if cf is None or value is None:
                continue
            if cf.data_type == "date" and isinstance(value, str):
                value = date.fromisoformat(value)
            kwargs[cf.slot_key] = value
    return BankTransaction(**kwargs)


def _extract_column_names(columns_json: list) -> list[str]:
    """从 columns_json 提取列名字符串。

    支持两种存储格式：
    - list[str]：直接作为列名（如 ["日期","摘要","科目","金额"]）。
    - list[dict]：从 dict 的 name / label / col 键取列名。
    """
    names: list[str] = []
    for col in columns_json:
        if isinstance(col, str):
            names.append(col)
        elif isinstance(col, dict):
            name = col.get("name") or col.get("label") or col.get("col")
            if name:
                names.append(str(name))
    return names


def _journal_columns_from_template(db: Session, version_id: str | None) -> list[str]:
    """若绑定了日记账模板版本且该版本有 columns_json，返回列名列表；否则返回空列表。"""
    if not version_id:
        return []
    v = db.get(CompanyJournalTemplateVersion, version_id)
    if v is None or not v.columns_json:
        return []
    return _extract_column_names(v.columns_json)


def _journal_columns_from_rows_data(rows: list[JournalPreviewRowData]) -> list[str]:
    """从内存预览行的 output_values 键并集（首次出现顺序）提取列名，过滤 _ 前缀内部键。"""
    seen: dict[str, None] = {}
    for row in rows:
        for key in row.output_values:
            if not key.startswith("_"):
                seen[key] = None
    return list(seen.keys())


def _journal_columns_from_rows_db(rows: list[JournalPreviewRow]) -> list[str]:
    """从 DB 预览行的 output_values_json 键并集（首次出现顺序）提取列名，过滤 _ 前缀内部键。"""
    seen: dict[str, None] = {}
    for row in rows:
        for key in (row.output_values_json or {}):
            if not key.startswith("_"):
                seen[key] = None
    return list(seen.keys())


def _summary_from_json(raw: dict[str, object] | None) -> ConversionRunSummary:
    d = raw or {}
    return ConversionRunSummary(
        total_rows=int(d.get("total_rows", 0)),
        parse_failed_rows=int(d.get("parse_failed_rows", 0)),
        auto_confirmed_rows=int(d.get("auto_confirmed_rows", 0)),
        needs_confirmation_rows=int(d.get("needs_confirmation_rows", 0)),
        conflict_rows=int(d.get("conflict_rows", 0)),
    )


def list_conversion_runs(
    db: Session,
    company_id: str | None = None,
    accessible: set[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Page[ConversionRunListItemResponse]:
    """返回所有批次（不含预览行），按创建时间倒序，支持分页。

    accessible 为 None 表示跨公司角色（不过滤）；为集合时仅返回集合内公司的批次
    （空集合→ in_([])→空结果，符合最小权限原则）。
    """
    base = db.query(ConversionRun)
    if company_id is not None:
        base = base.filter(ConversionRun.company_id == company_id)
    if accessible is not None:
        base = base.filter(ConversionRun.company_id.in_(accessible))
    total = base.count()
    runs = (
        base.order_by(ConversionRun.created_at.desc(), ConversionRun.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
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
    return Page(items=items, total=total, limit=limit, offset=offset)


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


def list_preview_rows(
    db: Session, run_id: str, limit: int, offset: int, status: str | None = None
) -> Page[JournalPreviewRowData]:
    """分页返回某批次的日记账预览行，按 row_index 升序。status 非 None 时按状态过滤。"""
    base = db.query(JournalPreviewRow).filter(JournalPreviewRow.conversion_run_id == run_id)
    if status:
        base = base.filter(JournalPreviewRow.status == status)
    total = base.count()
    rows = base.order_by(JournalPreviewRow.row_index).offset(offset).limit(limit).all()
    return Page[JournalPreviewRowData](
        items=[_preview_row_to_data(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
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
    # 优先从绑定的日记账模板版本取列定义；无绑定则从持久化预览行键并集回退。
    journal_cols = _journal_columns_from_template(db, run.company_journal_template_version_id)
    if not journal_cols:
        journal_cols = _journal_columns_from_rows_db(rows)

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
        journal_columns=journal_cols,
    )
