"""任务 16A：路由守卫集成测试。

覆盖三类代表性场景：
- 无 token → 401。
- 角色权限不足 → 403（processor 命中 TEMPLATE_MANAGE 创建；processor 命中 AUDIT_VIEW 列表）。
- 跨公司写入 → 403（template_admin 仅授权 company-1，却尝试在 company-2 下创建）。

请求体使用能通过 schema 校验的真实形状，确保请求抵达守卫（得到 401/403 而非 422）。
"""

_BANK_TEMPLATE_BODY = {
    "name": "守卫测试模板",
    "version": {"file_type": "csv", "amount_mode": "income_expense_columns"},
}


def test_upload_requires_auth(client_with_db):
    c, _ = client_with_db
    r = c.post("/api/files/upload", data={"company_id": "company-1"})
    assert r.status_code == 401


def test_conversion_run_requires_auth(client_with_db):
    c, _ = client_with_db
    r = c.post(
        "/api/tools/bank-journal/conversion-runs",
        json={
            "company_id": "company-1",
            "bank_account_id": "bank-account-1",
            "source_file_ids": [],
            "bank_parse_config": {
                "file_type": "csv",
                "sheet_name": "Sheet1",
                "header_row_index": 0,
                "data_start_row_index": 1,
                "field_aliases": {},
                "amount_mode": "income_expense_columns",
                "amount_config": {},
                "date_formats": [],
            },
            "mappings": [],
            "rules": [],
            "required_columns": [],
        },
    )
    assert r.status_code == 401


def test_audit_requires_audit_view(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"])  # 无 AUDIT_VIEW
    r = c.get("/api/audit-logs", headers=auth_headers(user))
    assert r.status_code == 403


def test_template_create_denied_for_processor(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"], company_ids=["company-1"])  # 无 TEMPLATE_MANAGE
    r = c.post(
        "/api/tools/bank-journal/bank-templates",
        headers=auth_headers(user),
        json={"company_id": "company-1", **_BANK_TEMPLATE_BODY},
    )
    assert r.status_code == 403


def test_cross_company_write_denied(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["template_admin"], company_ids=["company-1"])
    r = c.post(
        "/api/tools/bank-journal/bank-templates",
        headers=auth_headers(user),
        json={"company_id": "company-2", **_BANK_TEMPLATE_BODY},
    )
    assert r.status_code == 403
