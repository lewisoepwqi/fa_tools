"""P0-1 / P2-4: 版本化编辑 + 停用启用 + 规则重排端点测试。

覆盖 4 个版本化实体（银行模板 / 日记账模板 / 映射方案 / 规则）：
- POST /{id}/versions 创建新版本（version_no 递增，旧版本不变）
- GET  /{id}/versions 版本历史
- PATCH /{id}/status 停用/启用
- POST /api/tools/bank-journal/rules/reorder 批量调整优先级
- 审计记录 modified / disabled / enabled / priority_changed
"""

import pytest

# ---------------------------------------------------------------------------
# 银行模板：新版本 + 版本历史 + 停用
# ---------------------------------------------------------------------------


def _create_bank_template(client) -> dict:
    return client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": "中国银行 CSV",
            "bank_name": "中国银行",
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


def test_bank_template_create_new_version() -> None:
    pass


def test_create_bank_template_new_version_increments_version_no(client) -> None:
    created = _create_bank_template(client)
    assert created["latest_version"]["version_no"] == 1

    response = client.post(
        f"/api/tools/bank-journal/bank-templates/{created['id']}/versions",
        json={
            "file_type": "csv",
            "header_row_index": 0,
            "data_start_row_index": 1,
            "field_aliases_json": {"交易日期": "transaction_date", "摘要": "summary"},
            "amount_mode": "income_expense_columns",
            "created_by": "user-1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["latest_version"]["version_no"] == 2
    assert data["latest_version"]["field_aliases_json"]["摘要"] == "summary"


def test_bank_template_version_history(client) -> None:
    created = _create_bank_template(client)
    client.post(
        f"/api/tools/bank-journal/bank-templates/{created['id']}/versions",
        json={
            "file_type": "csv",
            "amount_mode": "income_expense_columns",
            "created_by": "user-1",
        },
    )

    response = client.get(f"/api/tools/bank-journal/bank-templates/{created['id']}/versions")

    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 2
    assert versions[0]["version_no"] == 2
    assert versions[1]["version_no"] == 1


def test_bank_template_disable_and_enable(client) -> None:
    created = _create_bank_template(client)

    disabled = client.patch(
        f"/api/tools/bank-journal/bank-templates/{created['id']}/status",
        params={"status": "inactive"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "inactive"

    enabled = client.patch(
        f"/api/tools/bank-journal/bank-templates/{created['id']}/status",
        params={"status": "active"},
    )
    assert enabled.json()["status"] == "active"


def test_bank_template_invalid_status_returns_422(client) -> None:
    created = _create_bank_template(client)
    response = client.patch(
        f"/api/tools/bank-journal/bank-templates/{created['id']}/status",
        params={"status": "deleted"},
    )
    assert response.status_code == 422


def test_bank_template_version_records_audit(client) -> None:
    created = _create_bank_template(client)
    client.post(
        f"/api/tools/bank-journal/bank-templates/{created['id']}/versions",
        json={"file_type": "csv", "amount_mode": "income_expense_columns", "created_by": "user-1"},
    )
    logs = client.get("/api/audit-logs").json()["items"]
    assert any(log["action"] == "bank_template.modified" for log in logs)


# ---------------------------------------------------------------------------
# 日记账模板：新版本 + 版本历史 + 停用
# ---------------------------------------------------------------------------


def _create_journal_template(client) -> dict:
    return client.post(
        "/api/tools/bank-journal/journal-templates",
        json={
            "company_id": "company-1",
            "name": "标准日记账",
            "version": {
                "file_type": "xlsx",
                "columns_json": ["日期", "摘要"],
                "required_columns_json": ["日期"],
                "created_by": "user-1",
            },
        },
    ).json()


def test_journal_template_new_version_and_history(client) -> None:
    created = _create_journal_template(client)

    response = client.post(
        f"/api/tools/bank-journal/journal-templates/{created['id']}/versions",
        json={
            "file_type": "xlsx",
            "columns_json": ["日期", "摘要", "科目"],
            "required_columns_json": ["日期", "科目"],
            "created_by": "user-1",
        },
    )
    assert response.json()["latest_version"]["version_no"] == 2

    history = client.get(
        f"/api/tools/bank-journal/journal-templates/{created['id']}/versions"
    ).json()
    assert len(history) == 2


def test_journal_template_disable(client) -> None:
    created = _create_journal_template(client)
    response = client.patch(
        f"/api/tools/bank-journal/journal-templates/{created['id']}/status",
        params={"status": "inactive"},
    )
    assert response.json()["status"] == "inactive"


# ---------------------------------------------------------------------------
# 映射方案：新版本 + 版本历史 + 停用
# ---------------------------------------------------------------------------


def _create_mapping_profile(client) -> dict:
    return client.post(
        "/api/tools/bank-journal/mapping-profiles",
        json={
            "company_id": "company-1",
            "name": "默认映射",
            "version": {"mappings_json": {"日期": "transaction_date"}, "created_by": "user-1"},
        },
    ).json()


def test_mapping_profile_new_version_and_history(client) -> None:
    created = _create_mapping_profile(client)

    response = client.post(
        f"/api/tools/bank-journal/mapping-profiles/{created['id']}/versions",
        json={
            "mappings_json": {"日期": "transaction_date", "摘要": "summary"},
            "created_by": "user-1",
        },
    )
    assert response.json()["latest_version"]["version_no"] == 2

    history = client.get(
        f"/api/tools/bank-journal/mapping-profiles/{created['id']}/versions"
    ).json()
    assert len(history) == 2


def test_mapping_profile_disable(client) -> None:
    created = _create_mapping_profile(client)
    response = client.patch(
        f"/api/tools/bank-journal/mapping-profiles/{created['id']}/status",
        params={"status": "inactive"},
    )
    assert response.json()["status"] == "inactive"


# ---------------------------------------------------------------------------
# 规则：新版本 + 版本历史 + 停用 + 重排
# ---------------------------------------------------------------------------


def _create_rule(client, name: str = "货款规则", priority: int = 10) -> dict:
    return client.post(
        "/api/tools/bank-journal/rules",
        json={
            "company_id": "company-1",
            "name": name,
            "version": {
                "priority": priority,
                "conditions_json": {
                    "all": [{"field": "summary", "op": "contains", "value": "货款"}]
                },
                "actions_json": {"set": {"account_subject": "银行存款"}},
                "created_by": "user-1",
            },
        },
    ).json()


def test_rule_new_version_and_history(client) -> None:
    created = _create_rule(client)

    response = client.post(
        f"/api/tools/bank-journal/rules/{created['id']}/versions",
        json={
            "priority": 10,
            "conditions_json": {"all": [{"field": "summary", "op": "contains", "value": "采购"}]},
            "actions_json": {"set": {"account_subject": "应付账款"}},
            "created_by": "user-1",
        },
    )
    assert response.json()["latest_version"]["version_no"] == 2

    history = client.get(f"/api/tools/bank-journal/rules/{created['id']}/versions").json()
    assert len(history) == 2


def test_rule_disable(client) -> None:
    created = _create_rule(client)
    response = client.patch(
        f"/api/tools/bank-journal/rules/{created['id']}/status",
        params={"status": "inactive"},
    )
    assert response.json()["status"] == "inactive"


def test_rule_reorder_creates_new_priorities(client) -> None:
    rule_a = _create_rule(client, name="规则A", priority=10)
    rule_b = _create_rule(client, name="规则B", priority=20)

    response = client.post(
        "/api/tools/bank-journal/rules/reorder",
        json={
            "items": [
                {"rule_id": rule_a["id"], "priority": 5},
                {"rule_id": rule_b["id"], "priority": 1},
            ]
        },
    )

    assert response.status_code == 200
    updated = response.json()["updated"]
    assert len(updated) == 2

    # 验证新版本 priority 生效
    latest_a = client.get(f"/api/tools/bank-journal/rules/{rule_a['id']}").json()
    latest_b = client.get(f"/api/tools/bank-journal/rules/{rule_b['id']}").json()
    assert latest_a["latest_version"]["priority"] == 5
    assert latest_b["latest_version"]["priority"] == 1

    # 审计记录 rule.priority_changed
    logs = client.get("/api/audit-logs").json()["items"]
    assert any(log["action"] == "rule.priority_changed" for log in logs)


def test_rule_reorder_404_for_unknown_rule(client) -> None:
    response = client.post(
        "/api/tools/bank-journal/rules/reorder",
        json={"items": [{"rule_id": "no-such-rule", "priority": 1}]},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 规则 reorder 审计公司归属修复（W5 Task 6）
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_two_rules_same_company(client):
    """创建两条同公司规则，返回 (rule_a_id, rule_b_id, company_id)。"""
    rule_a = _create_rule(client, name="重排规则A", priority=10)
    rule_b = _create_rule(client, name="重排规则B", priority=20)
    return rule_a["id"], rule_b["id"], "company-1"


def test_reorder_audit_records_company(client, seed_two_rules_same_company) -> None:
    """reorder 审计事件 company_id 应等于被重排规则的公司，而非 None。"""
    rule_a_id, rule_b_id, company_id = seed_two_rules_same_company
    resp = client.post(
        "/api/tools/bank-journal/rules/reorder",
        json={
            "items": [
                {"rule_id": rule_a_id, "priority": 5},
                {"rule_id": rule_b_id, "priority": 1},
            ]
        },
    )
    assert resp.status_code == 200
    # audit-logs 不支持 action 过滤，取全部后在 Python 层筛选
    logs = client.get("/api/audit-logs").json()["items"]
    priority_changed = [log for log in logs if log["action"] == "rule.priority_changed"]
    assert priority_changed, "未找到 rule.priority_changed 审计条目"
    bad = [log["company_id"] for log in priority_changed if log["company_id"] != company_id]
    assert not bad, f"审计条目 company_id 应为 {company_id!r}，实际含异常值: {bad}"
