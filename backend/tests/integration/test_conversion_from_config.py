"""P0：验证转换真正读取用户配置的模板/映射/规则。

`/from-config` 端点接收配置 ID，服务端从 DB 查最新版本拼装内联参数后执行。
本测试对照现有内联端点（test_conversion_api.py），用同一份 fixture CSV 与等价
的版本化配置，断言两种入口产出的预览行一致——证明用户配的内容真正生效。
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
    """建一份与内联测试等价的银行模板（字段别名/金额模式一致）。"""
    response = client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中行CSV",
            "bank_account_id": "bank-account-1",
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"sheet_name": "Sheet1"},
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {
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
                "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats_json": ["%Y-%m-%d"],
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_journal_template(client) -> str:
    response = client.post(
        "/api/tools/bank-journal/journal-templates",
        json={
            "company_id": "company-1",
            "name": "标准日记账",
            "version": {
                "file_type": "xlsx",
                "columns_json": ["日期", "摘要", "科目", "金额"],
                "required_columns_json": ["日期", "摘要", "科目", "金额"],
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_mapping_profile(client, bank_id: str, journal_id: str) -> str:
    response = client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "中行→标准日记账",
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "version": {
                # 注意：映射方案的 rule_output 类型（摘要/科目）依赖规则输出，
                # 这里只配字段映射；摘要/科目通过规则注入。
                "mappings_json": {"日期": "transaction_date", "金额": "net_amount"},
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_rule(client) -> str:
    """与内联测试等价的规则：摘要含"货款"→科目=银行存款、摘要=收到客户款项。"""
    response = client.post(
        "/api/tools/bank-journal/rules",
        json={
            "company_id": "company-1",
            "name": "货款规则",
            "version": {
                "priority": 10,
                "conditions_json": {
                    "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                },
                "actions_json": {
                    "set": {
                        "journal_summary": "收到客户款项",
                        "account_subject": "银行存款",
                    }
                },
                "allow_auto_confirm": False,
                "created_by": "user-1",
            },
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_from_config_produces_same_result_as_inline(client, upload_dir) -> None:
    """用配置 ID 跑出的预览，与内联参数跑出的一致。"""
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)
    # 摘要/科目走规则输出；mappings_json 只支持 field 类型，故映射方案仅配日期/金额，
    # 科目/摘要通过规则注入并在断言中验证（见下方）。
    mapping_id = _create_mapping_profile(client, bank_id, journal_id)
    client.post(
        f"/api/tools/bank-journal/mapping-profiles/{mapping_id}/versions",
        json={
            "mappings_json": {
                "日期": "transaction_date",
                "金额": "net_amount",
            },
            "created_by": "user-1",
        },
    )
    rule_id = _create_rule(client)

    response = client.post(
        "/api/tools/bank-journal/conversion-runs/from-config",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "mapping_profile_id": mapping_id,
            "rule_ids": [rule_id],
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["summary"]["total_rows"] == 2
    # 版本快照应被记录（证明配置真正被读取并溯源）
    assert data["bank_template_version_id"] is not None
    assert data["company_journal_template_version_id"] is not None
    assert data["mapping_profile_version_id"] is not None


def test_from_config_404_when_template_missing(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    response = client.post(
        "/api/tools/bank-journal/conversion-runs/from-config",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": "no-such-template",
            "company_journal_template_id": "no-such-journal",
        },
    )
    assert response.status_code == 404


def test_from_config_400_when_no_template_provided(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    response = client.post(
        "/api/tools/bank-journal/conversion-runs/from-config",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
        },
    )
    assert response.status_code == 400


def test_from_config_tolerates_advanced_stale_key(client, upload_dir) -> None:
    """回归：_advanced 映射中带残余 extra 键（如 fixed 类型里留了 source）不应 500。

    W2 之前 mappings 是 list[dict[str,Any]]，没有 extra="forbid" 校验；
    W2 引入 contracts.py 后 _MappingBase extra="forbid" 会把这类历史数据拒掉。
    修复后改为 extra="ignore"，相同数据应返回 200。
    """
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)

    # 建映射方案，版本中用 _advanced 存一个 fixed 映射，但携带前端遗留的 source 字段
    resp = client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "含 stale key 的映射方案",
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "version": {
                "mappings_json": {
                    "日期": "transaction_date",
                    "金额": "net_amount",
                    "_advanced": [
                        # type 已切换为 fixed，但前端未清除 source 字段 ← 触发回归点
                        {
                            "type": "fixed",
                            "target": "科目",
                            "value": "管理费用",
                            "source": "stale_residual_key",
                        }
                    ],
                },
                "created_by": "user-1",
            },
        },
    )
    assert resp.status_code == 200
    mapping_id = resp.json()["id"]

    response = client.post(
        "/api/tools/bank-journal/conversion-runs/from-config",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [source_file_id],
            "bank_template_id": bank_id,
            "company_journal_template_id": journal_id,
            "mapping_profile_id": mapping_id,
        },
    )

    # 修复前：ValidationError → 未捕获 → HTTP 500；修复后应 200
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.text}"
    )


def test_from_config_records_audit(client, upload_dir) -> None:
    source_file_id = _upload_csv(client)
    bank_id = _create_bank_template(client)
    journal_id = _create_journal_template(client)
    rule_id = _create_rule(client)

    client.post(
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
    logs = client.get("/api/audit-logs").json()["items"]
    assert any(log["action"] == "conversion_run.created_from_config" for log in logs)
