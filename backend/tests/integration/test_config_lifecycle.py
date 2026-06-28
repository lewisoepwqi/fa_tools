"""配置实体生命周期：软删除 + 引用拦截测试。

覆盖 4 类配置的删除行为：
- 未被批次引用 → DELETE 204 → 状态变 deleted → 列表/下拉不再返回
- 被批次引用 → DELETE 409（保证历史可追溯，PRD §10.3.3）
"""

from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.fixture()
def upload_dir(monkeypatch, tmp_path):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    yield tmp_path / "uploads"
    get_settings.cache_clear()


FIXTURE = Path(__file__).parents[1] / "fixtures" / "bank_statement_basic.csv"


def _upload_csv(client) -> str:
    response = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_bank_template(client) -> str:
    return client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中行CSV",
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"sheet_name": "Sheet1"},
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {"交易日期": "transaction_date", "收入": "income_amount"},
                "amount_mode": "income_expense_columns",
                "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats_json": ["%Y-%m-%d"],
                "created_by": "user-1",
            },
        },
    ).json()["id"]


def _create_journal_template(client) -> str:
    return client.post(
        "/api/tools/bank-journal/journal-templates",
        json={
            "company_id": "company-1",
            "name": "标准日记账",
            "version": {
                "file_type": "xlsx",
                "columns_json": ["日期"],
                "required_columns_json": ["日期"],
                "created_by": "user-1",
            },
        },
    ).json()["id"]


def _create_rule(client, name: str = "货款规则") -> str:
    return client.post(
        "/api/tools/bank-journal/rules",
        json={
            "company_id": "company-1",
            "name": name,
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
    ).json()["id"]


# ---------------------------------------------------------------------------
# 软删除：未被引用可删，列表过滤
# ---------------------------------------------------------------------------


def test_delete_bank_template_unreferenced(client) -> None:
    bank_id = _create_bank_template(client)
    response = client.delete(f"/api/tools/bank-journal/bank-templates/{bank_id}")
    assert response.status_code == 204

    # 列表不再返回
    listed = client.get("/api/tools/bank-journal/bank-templates").json()
    assert all(t["id"] != bank_id for t in listed)


def test_delete_journal_template_unreferenced(client) -> None:
    journal_id = _create_journal_template(client)
    response = client.delete(f"/api/tools/bank-journal/journal-templates/{journal_id}")
    assert response.status_code == 204
    listed = client.get("/api/tools/bank-journal/journal-templates").json()
    assert all(t["id"] != journal_id for t in listed)


def test_delete_rule_unreferenced(client) -> None:
    rule_id = _create_rule(client)
    response = client.delete(f"/api/tools/bank-journal/rules/{rule_id}")
    assert response.status_code == 204
    listed = client.get("/api/tools/bank-journal/rules").json()
    assert all(t["id"] != rule_id for t in listed)


def test_delete_mapping_profile_unreferenced(client) -> None:
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)
    profile_id = client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "映射A",
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "version": {"mappings_json": {"日期": "transaction_date"}, "created_by": "user-1"},
        },
    ).json()["id"]
    response = client.delete(f"/api/tools/bank-journal/mapping-profiles/{profile_id}")
    assert response.status_code == 204
    listed = client.get("/api/tools/bank-journal/mapping-profiles").json()
    assert all(t["id"] != profile_id for t in listed)


# ---------------------------------------------------------------------------
# 引用拦截：被批次引用不可删
# ---------------------------------------------------------------------------


def test_delete_bank_template_referenced_by_run_returns_409(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)
    # 用 from-config 跑一次，会在 ConversionRun 写入 bank_template_version_id
    run = client.post(
        "/api/tools/bank-journal/conversion-runs/from-config",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
        },
    )
    assert run.status_code == 200

    response = client.delete(f"/api/tools/bank-journal/bank-templates/{bank_id}")
    assert response.status_code == 409
    assert "引用" in response.json()["detail"]


def test_delete_rule_referenced_by_run_returns_409(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)
    rule_id = _create_rule(client)
    # from-config 带规则，会在 ConversionRunRuleVersion 写入 rule_version_id（NOT NULL）
    run = client.post(
        "/api/tools/bank-journal/conversion-runs/from-config",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "rule_ids": [rule_id],
        },
    )
    assert run.status_code == 200

    response = client.delete(f"/api/tools/bank-journal/rules/{rule_id}")
    assert response.status_code == 409
    assert "引用" in response.json()["detail"]


def test_delete_template_referenced_by_mapping_returns_409(client) -> None:
    """模板被映射方案引用时，删除应提示先处理映射方案。"""
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)
    client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "映射A",
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "version": {"mappings_json": {"日期": "transaction_date"}, "created_by": "user-1"},
        },
    )
    response = client.delete(f"/api/tools/bank-journal/bank-templates/{bank_id}")
    assert response.status_code == 409
    assert "映射方案" in response.json()["detail"]


def test_delete_records_audit(client) -> None:
    bank_id = _create_bank_template(client)
    client.delete(f"/api/tools/bank-journal/bank-templates/{bank_id}")
    logs = client.get("/api/audit-logs").json()
    assert any(log["action"] == "bank_template.deleted" for log in logs)
