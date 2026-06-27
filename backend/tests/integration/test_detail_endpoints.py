"""详情/列表 GET 端点测试。

覆盖 5 个实体的详情端点 + conversion-runs 列表端点。所有端点均为只读、
不记审计。详情按 id 查询，不存在时返回 404（符合"未知 id → 404"约定）。
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


# ---------------------------------------------------------------------------
# 处理批次 conversion-runs：列表 + 详情
# ---------------------------------------------------------------------------


def _create_run(client) -> dict:
    upload = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()
    return client.post(
        "/api/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [upload["id"]],
            "bank_parse_config": {
                "file_type": "csv",
                "sheet_name": "Sheet1",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases": {
                    "交易日期": "transaction_date",
                    "入账日期": "posting_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                    "余额": "balance",
                    "对方户名": "counterparty_name",
                    "对方账号": "counterparty_account_no",
                    "摘要": "summary",
                    "用途": "purpose",
                    "流水号": "bank_transaction_id",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [
                {"target": "日期", "type": "field", "source": "transaction_date"},
                {"target": "摘要", "type": "rule_output", "source": "journal_summary"},
                {"target": "科目", "type": "rule_output", "source": "account_subject"},
                {"target": "金额", "type": "field", "source": "net_amount"},
            ],
            "rules": [
                {
                    "id": "rule-1",
                    "version_id": "rule-version-1",
                    "priority": 10,
                    "conditions": {
                        "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                    },
                    "actions": [
                        {"field": "journal_summary", "value": "收到客户款项"},
                        {"field": "account_subject", "value": "银行存款"},
                    ],
                    "allow_auto_confirm": False,
                }
            ],
            "required_columns": ["日期", "摘要", "科目", "金额"],
        },
    ).json()


def test_list_conversion_runs_returns_items_without_preview_rows(client, upload_dir) -> None:
    created = _create_run(client)

    response = client.get("/api/conversion-runs")

    assert response.status_code == 200
    items = response.json()
    assert any(item["id"] == created["id"] for item in items)
    matched = next(item for item in items if item["id"] == created["id"])
    # 列表项不应携带预览行（避免大响应）
    assert "preview_rows" not in matched
    assert matched["company_id"] == "company-1"
    assert matched["bank_account_id"] == "bank-account-1"
    assert matched["summary"]["total_rows"] == 2
    assert matched["created_at"] is not None


def test_list_conversion_runs_filter_by_company(client, upload_dir) -> None:
    _create_run(client)

    response = client.get("/api/conversion-runs", params={"company_id": "company-1"})
    response_other = client.get("/api/conversion-runs", params={"company_id": "no-such-company"})

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response_other.json() == []


def test_get_conversion_run_detail_returns_preview_rows(client, upload_dir) -> None:
    created = _create_run(client)

    response = client.get(f"/api/conversion-runs/{created['id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == created["id"]
    assert detail["summary"]["total_rows"] == 2
    assert len(detail["preview_rows"]) == 2
    # 详情带主数据字段
    assert detail["company_id"] == "company-1"
    assert detail["created_at"] is not None
    # 预览行字段映射正确（模型 *_json 列 → schema 无后缀字段）
    first = detail["preview_rows"][0]
    assert set(first.keys()) == {
        "id",
        "row_index",
        "output_values",
        "status",
        "exception_codes",
        "matched_rule_version_ids",
        "rule_trace",
    }
    assert first["id"] is not None
    assert "日期" in first["output_values"]


def test_get_conversion_run_detail_404_when_missing(client) -> None:
    response = client.get("/api/conversion-runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 银行模板 bank-templates：详情
# ---------------------------------------------------------------------------


def _create_bank_template(client) -> dict:
    return client.post(
        "/api/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中国银行 CSV",
            "bank_name": "中国银行",
            "bank_account_id": "bank-account-1",
            "version": {
                "file_type": "csv",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {"交易日期": "transaction_date"},
                "amount_mode": "income_expense_columns",
                "created_by": "user-1",
            },
        },
    ).json()


def test_get_bank_template_detail(client) -> None:
    created = _create_bank_template(client)

    response = client.get(f"/api/bank-templates/{created['id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == created["id"]
    assert detail["name"] == "中国银行 CSV"
    assert detail["latest_version"]["version_no"] == 1
    assert detail["latest_version"]["field_aliases_json"] == {"交易日期": "transaction_date"}


def test_get_bank_template_detail_404_when_missing(client) -> None:
    assert client.get("/api/bank-templates/nope").status_code == 404


# ---------------------------------------------------------------------------
# 日记账模板 journal-templates：详情
# ---------------------------------------------------------------------------


def _create_journal_template(client) -> dict:
    return client.post(
        "/api/journal-templates",
        json={
            "company_id": "company-1",
            "name": "标准日记账",
            "version": {
                "file_type": "xlsx",
                "sheet_name": "日记账",
                "columns_json": ["日期", "摘要", "科目", "金额"],
                "required_columns_json": ["日期", "科目", "金额"],
                "created_by": "user-1",
            },
        },
    ).json()


def test_get_journal_template_detail(client) -> None:
    created = _create_journal_template(client)

    response = client.get(f"/api/journal-templates/{created['id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == created["id"]
    assert detail["latest_version"]["version_no"] == 1
    assert detail["latest_version"]["required_columns_json"] == ["日期", "科目", "金额"]


def test_get_journal_template_detail_404_when_missing(client) -> None:
    assert client.get("/api/journal-templates/nope").status_code == 404


# ---------------------------------------------------------------------------
# 映射方案 mapping-profiles：详情
# ---------------------------------------------------------------------------


def _create_mapping_profile(client) -> dict:
    return client.post(
        "/api/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "默认映射",
            "version": {
                "mappings_json": {"日期": "transaction_date"},
                "created_by": "user-1",
            },
        },
    ).json()


def test_get_mapping_profile_detail(client) -> None:
    created = _create_mapping_profile(client)

    response = client.get(f"/api/mapping-profiles/{created['id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == created["id"]
    assert detail["latest_version"]["version_no"] == 1
    assert detail["latest_version"]["mappings_json"] == {"日期": "transaction_date"}


def test_get_mapping_profile_detail_404_when_missing(client) -> None:
    assert client.get("/api/mapping-profiles/nope").status_code == 404


# ---------------------------------------------------------------------------
# 规则 rules：详情
# ---------------------------------------------------------------------------


def _create_rule(client) -> dict:
    return client.post(
        "/api/rules",
        json={
            "company_id": "company-1",
            "name": "货款收入规则",
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


def test_get_rule_detail(client) -> None:
    created = _create_rule(client)

    response = client.get(f"/api/rules/{created['id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == created["id"]
    assert detail["latest_version"]["version_no"] == 1
    assert detail["latest_version"]["priority"] == 10
    assert detail["latest_version"]["allow_auto_confirm"] is False


def test_get_rule_detail_404_when_missing(client) -> None:
    assert client.get("/api/rules/nope").status_code == 404


# ---------------------------------------------------------------------------
# P0-2: 转换批次快照模板/映射版本 ID
# ---------------------------------------------------------------------------


def test_conversion_run_snapshots_version_ids(client, upload_dir) -> None:
    """转换批次可携带使用的模板/映射版本 ID，用于后续追溯（PRD §10.3.3）。"""
    upload = client.post(
        "/api/files/upload",
        files={"file": ("bank_statement_basic.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"company_id": "company-1", "uploaded_by": "user-1"},
    ).json()
    response = client.post(
        "/api/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [upload["id"]],
            "bank_template_version_id": "btv-1",
            "company_journal_template_version_id": "cjtv-1",
            "mapping_profile_version_id": "mpv-1",
            "bank_parse_config": {
                "file_type": "csv",
                "sheet_name": "Sheet1",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases": {
                    "交易日期": "transaction_date",
                    "收入": "income_amount",
                    "支出": "expense_amount",
                },
                "amount_mode": "income_expense_columns",
                "amount_config": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats": ["%Y-%m-%d"],
            },
            "mappings": [{"target": "日期", "type": "field", "source": "transaction_date"}],
            "rules": [],
            "required_columns": ["日期"],
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["bank_template_version_id"] == "btv-1"
    assert created["company_journal_template_version_id"] == "cjtv-1"
    assert created["mapping_profile_version_id"] == "mpv-1"

    # 详情端点也应返回版本快照
    detail = client.get(f"/api/conversion-runs/{created['id']}").json()
    assert detail["bank_template_version_id"] == "btv-1"

    # 列表端点也应返回版本快照
    items = client.get("/api/conversion-runs").json()
    matched = next(item for item in items if item["id"] == created["id"])
    assert matched["mapping_profile_version_id"] == "mpv-1"
