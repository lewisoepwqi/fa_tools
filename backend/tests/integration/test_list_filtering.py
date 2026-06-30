"""list 端点的过滤查询参数测试。

覆盖解耦后的反向关联能力（PRD：模板详情页查看"被哪些映射引用"）：
- GET /mapping-profiles?bank_template_id=... / ?company_journal_template_id=...
- GET /rules?scope_type=... &scope_id=...

复用 test_config_lifecycle 的工厂，但内联以保持本文件自包含。
"""

from app.core.enums import RecordStatus  # noqa: F401  仅为表明枚举语义，便于阅读


def _create_bank_template(client, name: str = "中行CSV") -> str:
    return client.post(
        "/api/tools/bank-journal/bank-templates",
        json={
            "company_id": "company-1",
            "name": name,
            "version": {
                "file_type": "csv",
                "sheet_selector_json": {"sheet_name": "Sheet1"},
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases_json": {"交易日期": "transaction_date"},
                "amount_mode": "income_expense_columns",
                "amount_config_json": {"income": "income_amount", "expense": "expense_amount"},
                "date_formats_json": ["%Y-%m-%d"],
                "created_by": "user-1",
            },
        },
    ).json()["id"]


def _create_journal_template(client, name: str = "标准日记账") -> str:
    return client.post(
        "/api/tools/bank-journal/journal-templates",
        json={
            "company_id": "company-1",
            "name": name,
            "version": {
                "file_type": "xlsx",
                "columns_json": ["日期"],
                "required_columns_json": ["日期"],
                "created_by": "user-1",
            },
        },
    ).json()["id"]


def _create_mapping(
    client,
    *,
    bank_template_id: str | None = None,
    journal_template_id: str | None = None,
    name: str = "映射A",
) -> str:
    payload: dict = {
        "company_id": "company-1",
        "name": name,
        "version": {"mappings_json": {"日期": "transaction_date"}, "created_by": "user-1"},
    }
    if bank_template_id is not None:
        payload["bank_template_id"] = bank_template_id
    if journal_template_id is not None:
        payload["company_journal_template_id"] = journal_template_id
    return client.post("/api/tools/bank-journal/mapping-profiles", json=payload).json()["id"]


def _create_rule(client, *, name: str = "规则", scope_type: str | None = None,
                 scope_id: str | None = None) -> str:
    payload: dict = {
        "company_id": "company-1",
        "name": name,
        "version": {
            "priority": 10,
            "conditions_json": {"all": [{"field": "summary", "op": "contains", "value": "货款"}]},
            "actions_json": {"set": {"account_subject": "银行存款"}},
            "allow_auto_confirm": False,
            "created_by": "user-1",
        },
    }
    if scope_type is not None:
        payload["scope_type"] = scope_type
    if scope_id is not None:
        payload["scope_id"] = scope_id
    return client.post("/api/tools/bank-journal/rules", json=payload).json()["id"]


# ---------------------------------------------------------------------------
# 映射方案：按 bank_template_id / company_journal_template_id 过滤
# ---------------------------------------------------------------------------


def test_list_mappings_filter_by_bank_template(client) -> None:
    bank_a = _create_bank_template(client, "中行A")
    bank_b = _create_bank_template(client, "建行B")
    journal = _create_journal_template(client)
    m1 = _create_mapping(
        client, bank_template_id=bank_a, journal_template_id=journal, name="映射A"
    )
    _m2 = _create_mapping(
        client, bank_template_id=bank_b, journal_template_id=journal, name="映射B"
    )

    listed = client.get(
        "/api/tools/bank-journal/mapping-profiles", params={"bank_template_id": bank_a}
    ).json()
    assert [m["id"] for m in listed["items"]] == [m1]


def test_list_mappings_filter_by_journal_template(client) -> None:
    bank = _create_bank_template(client)
    journal_a = _create_journal_template(client, "日记账A")
    journal_b = _create_journal_template(client, "日记账B")
    m1 = _create_mapping(
        client, bank_template_id=bank, journal_template_id=journal_a, name="映射A"
    )
    _m2 = _create_mapping(
        client, bank_template_id=bank, journal_template_id=journal_b, name="映射B"
    )

    listed = client.get(
        "/api/tools/bank-journal/mapping-profiles",
        params={"company_journal_template_id": journal_a},
    ).json()
    assert [m["id"] for m in listed["items"]] == [m1]


def test_list_mappings_filter_excludes_unbound(client) -> None:
    """按模板过滤时，模板外键为 NULL 的映射不应返回。"""
    bank = _create_bank_template(client)
    journal = _create_journal_template(client)
    bound = _create_mapping(client, bank_template_id=bank, journal_template_id=journal, name="绑定")
    _unbound = _create_mapping(client, name="未绑定")  # 两外键都空

    listed = client.get(
        "/api/tools/bank-journal/mapping-profiles", params={"bank_template_id": bank}
    ).json()
    assert [m["id"] for m in listed["items"]] == [bound]


def test_list_mappings_no_filter_returns_all(client) -> None:
    """不带过滤参数时行为不变：返回全部（含未绑定）。"""
    bank = _create_bank_template(client)
    journal = _create_journal_template(client)
    bound = _create_mapping(
        client, bank_template_id=bank, journal_template_id=journal, name="绑定"
    )
    unbound = _create_mapping(client, name="未绑定")

    listed = client.get("/api/tools/bank-journal/mapping-profiles").json()
    listed_ids = {m["id"] for m in listed["items"]}
    # 测试夹具预置了 mp-1；本测试另建 2 条，共 ≥ 2 条；仅断言本测试创建的都在列表中
    assert {bound, unbound} <= listed_ids


# ---------------------------------------------------------------------------
# 规则：按 scope_type / scope_id 过滤
# ---------------------------------------------------------------------------


def test_list_rules_filter_by_scope(client) -> None:
    bank_id = _create_bank_template(client)
    r1 = _create_rule(client, name="绑定规则", scope_type="bank_template", scope_id=bank_id)
    _r2 = _create_rule(client, name="全局规则")  # scope 全空

    listed = client.get(
        "/api/tools/bank-journal/rules",
        params={"scope_type": "bank_template", "scope_id": bank_id},
    ).json()
    assert [r["id"] for r in listed["items"]] == [r1]


def test_list_rules_no_filter_returns_all(client) -> None:
    bank_id = _create_bank_template(client)
    r1 = _create_rule(client, name="绑定规则", scope_type="bank_template", scope_id=bank_id)
    r2 = _create_rule(client, name="全局规则")

    listed = client.get("/api/tools/bank-journal/rules").json()
    listed_ids = {r["id"] for r in listed["items"]}
    # 测试夹具预置了 rule-1/r1/rule-auto；本测试另建 2 条；仅断言本测试创建的都在列表中
    assert {r1, r2} <= listed_ids


# ---------------------------------------------------------------------------
# 回归：列表端点反映最新版本（N+1 优化后行为不变）
# ---------------------------------------------------------------------------


def test_list_bank_templates_reflects_latest_version(client) -> None:
    """创建第 2 版本后，列表项 latest_version.version_no 应为 2。"""
    tmpl_id = _create_bank_template(client, "中行CSV版本测试")
    client.post(
        f"/api/tools/bank-journal/bank-templates/{tmpl_id}/versions",
        json={
            "file_type": "csv",
            "header_row_index": 0,
            "data_start_row_index": 1,
            "field_aliases_json": {"交易日期": "transaction_date", "摘要": "summary"},
            "amount_mode": "income_expense_columns",
            "date_formats_json": ["%Y-%m-%d"],
            "created_by": "user-1",
        },
    )
    listed = client.get("/api/tools/bank-journal/bank-templates").json()
    match = next(m for m in listed["items"] if m["id"] == tmpl_id)
    assert match["latest_version"]["version_no"] == 2
