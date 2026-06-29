from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.api.deps import (
    CurrentUserDep,
    DbSession,
    require,
    require_company_access,
)
from app.core.config import get_settings
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event
from app.tools.bank_journal.enums import PreviewStatus
from app.tools.bank_journal.models.conversion import (
    ConversionRun,
    ConversionRunFile,
    ConversionRunRuleVersion,
    Export,
    JournalPreviewRow,
)
from app.tools.bank_journal.schemas.export import ExportCreate
from app.tools.bank_journal.services.export_service import (
    export_preview_rows_to_csv,
    export_preview_rows_to_xlsx,
    export_report_to_json,
    validate_required_columns,
)

router = APIRouter(tags=["exports"])


@router.post(
    "/api/tools/bank-journal/conversion-runs/{run_id}/exports",
    dependencies=[Depends(require(Permission.EXPORT_RUN))],
)
def create_export(
    run_id: str,
    payload: ExportCreate,
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
) -> dict:
    payload.exported_by = user.id
    run = db.query(ConversionRun).filter(ConversionRun.id == run_id).first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion run not found: {run_id}",
        )
    # 派生公司写校验：导出依附于批次，按批次公司校验
    require_company_access(user, run.company_id)

    output_dir = Path(get_settings().export_dir)
    export_id = str(uuid4())

    rows, row_count = _resolve_export_rows(db, run_id, payload)

    # P0-5: 必填字段完整性校验（PRD §6.9.4）
    required_columns = payload.required_columns or []
    if required_columns:
        violations = validate_required_columns(rows, required_columns)
        if violations:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "导出数据存在必填字段缺失",
                    "required_columns": required_columns,
                    "violating_row_indexes": violations,
                },
            )

    if payload.file_type == "xlsx":
        filename = f"{export_id}.xlsx"
        export_preview_rows_to_xlsx(rows, payload.columns, output_dir, filename)
    else:
        filename = f"{export_id}.csv"
        export_preview_rows_to_csv(rows, payload.columns, output_dir, filename)

    # P0-4: 生成处理报告（PRD §6.9.7）
    report = _build_export_report(db, run, rows, payload.exported_by)
    report_filename = f"{export_id}.report.json"
    export_report_to_json(report, output_dir, report_filename)

    export = Export(
        id=export_id,
        conversion_run_id=run_id,
        exported_by=payload.exported_by,
        file_type=payload.file_type,
        storage_key=filename,
        report_storage_key=report_filename,
        row_count=row_count,
        only_confirmed=payload.only_confirmed,
    )
    db.add(export)
    db.commit()

    response = {
        "export_id": export_id,
        "file_type": payload.file_type,
        "row_count": row_count,
        "download_url": f"/api/tools/bank-journal/exports/{export_id}/download",
        "report_url": f"/api/tools/bank-journal/exports/{export_id}/report",
    }
    record_audit_event(
        db,
        company_id=None,
        actor_id=user.id,
        action="export.created",
        entity_type="export",
        entity_id=export_id,
        after=response,
        **audit_ctx(request),
    )
    return response


def _resolve_export_rows(
    db: DbSession, run_id: str, payload: ExportCreate
) -> tuple[list[dict[str, object]], int]:
    """P0-3: 优先从库内 preview rows 取数（支持 only_confirmed 过滤）。

    若客户端显式传入 rows（历史用法），则直接使用客户端数据，不查库不过滤。
    """
    if payload.rows is not None:
        rows = list(payload.rows)
        return rows, len(rows)

    preview_rows = (
        db.query(JournalPreviewRow)
        .filter(JournalPreviewRow.conversion_run_id == run_id)
        .order_by(JournalPreviewRow.row_index.asc())
        .all()
    )
    rows: list[dict[str, object]] = []
    for row in preview_rows:
        if payload.only_confirmed and row.status not in _CONFIRMED_STATUSES:
            continue
        output = dict(row.output_values_json or {})
        # 剔除解析失败的内部元数据键，避免污染导出
        output = {k: v for k, v in output.items() if not k.startswith("_")}
        rows.append(output)
    return rows, len(rows)


_CONFIRMED_STATUSES = {
    PreviewStatus.AUTO_CONFIRMED.value,
    PreviewStatus.MANUALLY_CONFIRMED.value,
}


def _build_export_report(
    db: DbSession, run: ConversionRun, rows: list[dict[str, object]], exported_by: str | None
) -> dict[str, object]:
    """构建处理报告（PRD §6.9.7 的 11 项字段）。"""
    source_files = [
        result[0]
        for result in db.query(ConversionRunFile.source_file_id)
        .filter(ConversionRunFile.conversion_run_id == run.id)
        .all()
    ]
    rule_version_ids = [
        result[0]
        for result in db.query(ConversionRunRuleVersion.rule_version_id)
        .filter(ConversionRunRuleVersion.conversion_run_id == run.id)
        .all()
    ]

    all_preview_rows = (
        db.query(JournalPreviewRow)
        .filter(JournalPreviewRow.conversion_run_id == run.id)
        .all()
    )
    total = len(all_preview_rows)
    auto_confirmed = sum(
        1 for r in all_preview_rows if r.status == PreviewStatus.AUTO_CONFIRMED.value
    )
    manually_confirmed = sum(
        1 for r in all_preview_rows if r.status == PreviewStatus.MANUALLY_CONFIRMED.value
    )
    exception_rows = sum(
        1
        for r in all_preview_rows
        if (r.exception_codes_json or [])
    )

    return {
        "batch_id": run.id,
        "source_files": source_files,
        "bank_template_version_id": run.bank_template_version_id,
        "company_journal_template_version_id": run.company_journal_template_version_id,
        "mapping_profile_version_id": run.mapping_profile_version_id,
        "rule_version_ids": rule_version_ids,
        "total_rows": total,
        "success_rows": len(rows),
        "auto_confirmed_rows": auto_confirmed,
        "manually_confirmed_rows": manually_confirmed,
        "exception_rows": exception_rows,
        "exported_by": exported_by,
        "exported_at": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/api/tools/bank-journal/exports/{export_id}/download",
    dependencies=[Depends(require(Permission.EXPORT_RUN))],
)
def download_export(
    export_id: str, db: DbSession, user: CurrentUserDep
) -> FileResponse:
    export = db.query(Export).filter(Export.id == export_id).first()
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    _require_export_company_access(db, user, export)
    path = Path(get_settings().export_dir) / export.storage_key
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found"
        )
    return FileResponse(
        path,
        filename=export.storage_key,
        media_type="application/octet-stream",
    )


@router.get(
    "/api/tools/bank-journal/exports/{export_id}/report",
    dependencies=[Depends(require(Permission.EXPORT_RUN))],
)
def download_export_report(
    export_id: str, db: DbSession, user: CurrentUserDep
) -> FileResponse:
    """下载处理报告（PRD §6.9.7）。"""
    export = db.query(Export).filter(Export.id == export_id).first()
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    _require_export_company_access(db, user, export)
    if not export.report_storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not available"
        )
    path = Path(get_settings().export_dir) / export.report_storage_key
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found"
        )
    return FileResponse(
        path,
        filename=export.report_storage_key,
        media_type="application/json",
    )


def _require_export_company_access(db: DbSession, user: CurrentUserDep, export: Export) -> None:
    """加载导出所属批次 → 按批次公司做访问校验。

    区分两种 None：
    - export 本身不存在 → 由调用方在调用此函数前已检查并抛 404，此处不再处理。
    - export 存在但 run 已消失（孤儿）→ 无法确认归属，fail-closed：抛 403 而非放行。
    """
    run = (
        db.query(ConversionRun)
        .filter(ConversionRun.id == export.conversion_run_id)
        .first()
    )
    if run is None:
        # 孤儿导出：父批次已丢失，无法校验归属，拒绝访问
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法确认导出所属公司，拒绝访问",
        )
    require_company_access(user, run.company_id)
