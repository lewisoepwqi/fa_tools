"""TDD: Task 5 - RunStatus 状态机 + create/process 拆分 + 失败处理。

验证：解析阶段抛错时，run 应置 FAILED + error_message，而非整请求 500。
"""
from pathlib import Path

from app.tools.bank_journal.models.conversion import ConversionRun
from app.tools.bank_journal.schemas.conversion import BankParseConfig, ConversionRunCreate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_payload() -> ConversionRunCreate:
    """构造最小合法转换 payload（不依赖文件实际存在）。"""
    return ConversionRunCreate(
        company_id="company-1",
        bank_account_id="bank-account-1",
        source_file_ids=["file-1"],
        bank_parse_config=BankParseConfig(
            file_type="csv",
            sheet_name="Sheet1",
            header_row_index=0,
            data_start_row_index=1,
            field_aliases={},
            amount_mode="income_expense_columns",
            amount_config={"income": "income_amount", "expense": "expense_amount"},
            date_formats=["%Y-%m-%d"],
        ),
        mappings=[],
        rules=[],
        required_columns=[],
    )


def _upload_dir(tmp_path: Path) -> Path:
    d = tmp_path / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_process_run_failure_sets_failed_status(client_with_db, monkeypatch, tmp_path) -> None:
    """解析阶段抛错时，run 应置 failed + error_message，而非整请求 500。"""
    from app.tools.bank_journal.services import conversion_service

    c, db = client_with_db

    payload = _make_payload()

    # 第一步：建 pending run
    run = conversion_service.create_pending_run(db, payload)
    db.commit()
    assert run.status == "pending"

    # 注入解析失败
    def boom(*a, **k):
        raise ValueError("解析失败模拟")

    monkeypatch.setattr(conversion_service, "_parse_and_build_rows", boom, raising=False)

    # 第二步：执行处理，预期返回 failed 响应，不抛 500
    resp = conversion_service.process_conversion_run(db, run.id, _upload_dir(tmp_path), payload)

    assert resp.status == "failed"
    assert resp.error_message is not None and "解析失败" in resp.error_message

    # DB 中 run 记录也应标为 failed
    refreshed = db.get(ConversionRun, run.id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.error_message is not None and "解析失败" in refreshed.error_message


def test_create_pending_run_status_is_pending(client_with_db) -> None:
    """create_pending_run 建出的 run 状态为 pending。"""
    from app.tools.bank_journal.services import conversion_service

    _c, db = client_with_db
    payload = _make_payload()
    run = conversion_service.create_pending_run(db, payload)
    assert run.status == "pending"
    db.rollback()  # 清理，不落库


def _seed_failed_run(db, error: str):
    """直接插一条 failed 状态的 ConversionRun（不走解析流程）。"""
    import uuid

    from app.tools.bank_journal.models.conversion import ConversionRun

    run = ConversionRun(
        id=str(uuid.uuid4()),
        company_id="company-1",
        bank_account_id="bank-account-1",
        status="failed",
        error_message=error,
        summary_json={
            "total_rows": 0,
            "parse_failed_rows": 0,
            "auto_confirmed_rows": 0,
            "needs_confirmation_rows": 0,
            "conflict_rows": 0,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_failed_run_exposes_error_in_api(client_with_db, admin_auth) -> None:
    """failed 批次的详情与列表响应都带 error_message。"""
    c, db = client_with_db
    run = _seed_failed_run(db, error="解析失败：列缺失")

    detail = c.get(
        f"/api/tools/bank-journal/conversion-runs/{run.id}",
        headers=admin_auth,
    ).json()
    assert detail["status"] == "failed"
    assert detail["error_message"] == "解析失败：列缺失"

    listed = c.get(
        "/api/tools/bank-journal/conversion-runs",
        params={"company_id": run.company_id},
        headers=admin_auth,
    ).json()
    item = next(i for i in listed["items"] if i["id"] == run.id)
    assert item["error_message"] == "解析失败：列缺失"
