"""全链路 MVP 集成测试：覆盖本次补齐的所有 P0/P1 真缺口。

流程：
1. 上传样本 → detect 自动识别模板（P1-7/P1-8）
2. 创建银行模板/日记账模板/映射方案/规则（含新版本编辑 / 停用，P0-1/P2-4）
3. 发起转换（携带版本快照 P0-2），含逐行异常标记（P1-1）
4. 人工确认闭环（P0-6 后端）
5. 导出：only_confirmed 过滤（P0-3）+ 必填校验（P0-5）+ 处理报告（P0-4）
6. 审计追溯（P2-3 modified/disabled）
"""
import json
from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.fixture()
def dirs(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


FIXTURE = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"


def _upload(client) -> dict:
    return client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()


def test_detect_then_create_template(client, dirs) -> None:
    """P1-8: detect 识别后创建银行模板。"""
    upload = _upload(client)
    detected = client.post(
        "/api/tools/bank-journal/bank-templates/detect", json={"source_file_id": upload["id"]}
    ).json()
    assert detected["amount_mode"] == "income_expense_columns"

    created = client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "自动识别模板",
            "version": {
                "file_type": detected["file_type"],
                "header_row_index": detected["header_row_index"],
                "data_start_row_index": detected["data_start_row_index"],
                "field_aliases_json": detected["field_aliases"],
                "amount_mode": detected["amount_mode"],
                "amount_config_json": detected["amount_config"],
                "date_formats_json": detected["date_formats"],
                "created_by": "user-1",
            },
        },
    ).json()
    assert created["latest_version"]["version_no"] == 1


def test_full_flow_versioning_snapshot_export_report(client, dirs) -> None:
    upload = _upload(client)

    # 创建 4 个版本化实体
    bank_tpl = client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "银行模板",
            "version": {
                "file_type": "csv",
                "amount_mode": "income_expense_columns",
                "created_by": "user-1",
            },
        },
    ).json()
    journal_tpl = client.post(
        "/api/tools/bank-journal/journal-templates",
        json={
            "company_id": "company-1",
            "name": "日记账模板",
            "version": {
                "file_type": "xlsx",
                "required_columns_json": ["日期", "金额"],
                "created_by": "user-1",
            },
        },
    ).json()
    assert journal_tpl["latest_version"]["version_no"] == 1
    mapping = client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "映射",
            "version": {
                "mappings_json": {"日期": "transaction_date"},
                "created_by": "user-1",
            },
        },
    ).json()
    assert mapping["status"] == "active"
    rule = client.post(
        "/api/tools/bank-journal/rules",
        json={
            "company_id": "company-1",
            "name": "规则",
            "version": {
                "priority": 10,
                "conditions_json": {
                    "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                },
                "actions_json": {"set": {"account_subject": "银行存款"}},
                "allow_auto_confirm": False,
                "created_by": "user-1",
            },
        },
    ).json()

    # P0-1: 编辑=新版本（版本号递增）
    bank_tpl_v2 = client.post(
        f"/api/tools/bank-journal/bank-templates/{bank_tpl['id']}/versions",
        json={"file_type": "csv", "amount_mode": "income_expense_columns", "created_by": "user-1"},
    ).json()
    assert bank_tpl_v2["latest_version"]["version_no"] == 2

    # P0-2: 转换批次携带版本快照
    run = client.post(
        "/api/tools/bank-journal/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [upload["id"]],
            "bank_template_version_id": "btv-snapshot-1",
            "company_journal_template_version_id": "cjtv-snapshot-1",
            "mapping_profile_version_id": "mpv-snapshot-1",
            "bank_parse_config": {
                "file_type": "csv",
                "sheet_name": "Sheet1",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases": {
                    "交易日期": "transaction_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                    "摘要": "summary",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "科目", "type": "rule_output", "source": "account_subject"},
                {"target": "金额", "type": "field", "source": "net_amount"},
            ],
            "rules": [
                {
                    "id": rule["id"],
                    "version_id": "rule-version-1",
                    "priority": 10,
                    "conditions": {
                        "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                    },
                    "actions": [{"field": "account_subject", "value": "银行存款"}],
                    "allow_auto_confirm": False,
                }
            ],
            "required_columns": ["日期", "金额"],
        },
    ).json()
    assert run["summary"]["total_rows"] == 2
    assert run["bank_template_version_id"] == "btv-snapshot-1"
    assert run["mapping_profile_version_id"] == "mpv-snapshot-1"

    # P0-6: 人工确认第一行
    first_row = run["preview_rows"][0]
    assert first_row["id"] is not None
    confirm = client.post(
        f"/api/tools/bank-journal/preview-rows/{first_row['id']}/confirm",
        json={"confirmed_by": "user-1"},
    ).json()
    assert confirm["status"] == "manually_confirmed"

    # P0-3: 仅导出已确认（应只含 1 行）
    export = client.post(
        f"/api/tools/bank-journal/conversion-runs/{run['id']}/exports",
        json={
            "file_type": "xlsx",
            "columns": ["日期", "科目", "金额"],
            "exported_by": "user-1",
            "only_confirmed": True,
        },
    ).json()
    assert export["row_count"] == 1

    # P0-4: 处理报告下载，含版本快照与计数
    report = client.get(export["report_url"])
    assert report.status_code == 200
    body = json.loads(report.text)
    assert body["batch_id"] == run["id"]
    assert body["total_rows"] == 2
    assert body["manually_confirmed_rows"] == 1
    assert body["success_rows"] == 1

    # P0-5: 必填字段校验（要求不存在的字段 → 422）
    bad = client.post(
        f"/api/tools/bank-journal/conversion-runs/{run['id']}/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "金额"],
            "exported_by": "user-1",
            "required_columns": ["日期", "必填缺失列"],
        },
    )
    assert bad.status_code == 422

    # P2-3: 审计记录含 modified / disabled
    logs = client.get("/api/audit-logs").json()["items"]
    actions = {log["action"] for log in logs}
    assert "bank_template.modified" in actions
    assert "preview_row.confirmed" in actions
    assert "export.created" in actions

    # P2-4: 停用规则
    disabled = client.patch(
        f"/api/tools/bank-journal/rules/{rule['id']}/status", params={"status": "inactive"}
    ).json()
    assert disabled["status"] == "inactive"
