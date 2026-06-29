"""任务 16B：其余列表端点租户收窄 + 派生实体公司写校验。

覆盖：
- 列表收窄：bank_templates / journal_templates / mapping_profiles / rules /
  custom_fields / audit-logs，scoped 用户只看本公司，admin 看全部。
- 审计日志：NULL company_id 行为平台级，scoped 用户不可见。
- 派生写校验：预览行 PATCH/confirm、导出 创建/下载、自定义字段 PATCH/DELETE
  对他公司资源返回 403。
"""

from uuid import uuid4

from app.models.audit import AuditLog
from app.models.company import Company
from app.tools.bank_journal.models.conversion import (
    ConversionRun,
    Export,
    JournalPreviewRow,
)
from app.tools.bank_journal.models.custom_field import CustomField
from app.tools.bank_journal.models.mapping import MappingProfile, MappingProfileVersion
from app.tools.bank_journal.models.rule import Rule, RuleVersion
from app.tools.bank_journal.models.template import (
    BankTemplate,
    BankTemplateVersion,
    CompanyJournalTemplate,
    CompanyJournalTemplateVersion,
)


def _ensure_company(db, company_id):
    if db.get(Company, company_id) is None:
        db.add(Company(id=company_id, name=company_id))
        db.flush()


def _seed_bank_template(db, company_id):
    _ensure_company(db, company_id)
    tid = str(uuid4())
    db.add(BankTemplate(id=tid, company_id=company_id, name=f"bt-{tid}", status="active"))
    db.flush()
    db.add(
        BankTemplateVersion(
            id=str(uuid4()),
            bank_template_id=tid,
            version_no=1,
            file_type="csv",
            amount_mode="income_expense_columns",
        )
    )
    db.commit()
    return tid


def _seed_journal_template(db, company_id):
    _ensure_company(db, company_id)
    tid = str(uuid4())
    db.add(
        CompanyJournalTemplate(
            id=tid, company_id=company_id, name=f"cjt-{tid}", status="active"
        )
    )
    db.flush()
    db.add(
        CompanyJournalTemplateVersion(
            id=str(uuid4()),
            company_journal_template_id=tid,
            version_no=1,
            file_type="csv",
        )
    )
    db.commit()
    return tid


def _seed_mapping_profile(db, company_id):
    _ensure_company(db, company_id)
    pid = str(uuid4())
    db.add(
        MappingProfile(id=pid, company_id=company_id, name=f"mp-{pid}", status="active")
    )
    db.flush()
    db.add(MappingProfileVersion(id=str(uuid4()), mapping_profile_id=pid, version_no=1))
    db.commit()
    return pid


def _seed_rule(db, company_id):
    _ensure_company(db, company_id)
    rid = str(uuid4())
    db.add(Rule(id=rid, company_id=company_id, name=f"rule-{rid}", status="active"))
    db.flush()
    db.add(RuleVersion(id=str(uuid4()), rule_id=rid, version_no=1, priority=1))
    db.commit()
    return rid


def _seed_custom_field(db, company_id, slot_key="ext_text_1"):
    _ensure_company(db, company_id)
    cid = str(uuid4())
    db.add(
        CustomField(
            id=cid,
            company_id=company_id,
            field_key=f"fk_{cid[:8]}",
            name=f"cf-{cid[:8]}",
            slot_key=slot_key,
            data_type="text",
            header_keywords_json=[],
            status="active",
        )
    )
    db.commit()
    return cid


def _seed_run(db, company_id):
    _ensure_company(db, company_id)
    run_id = str(uuid4())
    db.add(ConversionRun(id=run_id, company_id=company_id, status="completed"))
    db.commit()
    return run_id


def _seed_preview_row(db, run_id):
    rid = str(uuid4())
    db.add(
        JournalPreviewRow(
            id=rid,
            conversion_run_id=run_id,
            row_index=0,
            status="needs_confirmation",
            output_values_json={},
        )
    )
    db.commit()
    return rid


# ---------------------------------------------------------------------------
# A. 列表收窄
# ---------------------------------------------------------------------------


def test_bank_templates_scoped(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_bank_template(db, "co-A")
    _seed_bank_template(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.get(
        "/api/tools/bank-journal/bank-templates", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert companies == {"co-A"}


def test_bank_templates_admin_sees_all(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_bank_template(db, "co-A")
    _seed_bank_template(db, "co-B")
    user = make_user(db, roles=["admin"])
    r = c.get(
        "/api/tools/bank-journal/bank-templates", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert {"co-A", "co-B"} <= companies


def test_journal_templates_scoped(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_journal_template(db, "co-A")
    _seed_journal_template(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.get(
        "/api/tools/bank-journal/journal-templates", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert companies == {"co-A"}


def test_mapping_profiles_scoped(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_mapping_profile(db, "co-A")
    _seed_mapping_profile(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.get(
        "/api/tools/bank-journal/mapping-profiles", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert companies == {"co-A"}


def test_mapping_profiles_admin_sees_all(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_mapping_profile(db, "co-A")
    _seed_mapping_profile(db, "co-B")
    user = make_user(db, roles=["admin"])
    r = c.get(
        "/api/tools/bank-journal/mapping-profiles", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert {"co-A", "co-B"} <= companies


def test_rules_scoped(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_rule(db, "co-A")
    _seed_rule(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.get("/api/tools/bank-journal/rules", headers=auth_headers(user))
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert companies == {"co-A"}


def test_rules_admin_sees_all(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_rule(db, "co-A")
    _seed_rule(db, "co-B")
    user = make_user(db, roles=["admin"])
    r = c.get("/api/tools/bank-journal/rules", headers=auth_headers(user))
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert {"co-A", "co-B"} <= companies


def test_custom_fields_scoped(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_custom_field(db, "co-A")
    _seed_custom_field(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.get(
        "/api/tools/bank-journal/custom-fields", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert companies == {"co-A"}


def test_custom_fields_admin_sees_all(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_custom_field(db, "co-A")
    _seed_custom_field(db, "co-B")
    user = make_user(db, roles=["admin"])
    r = c.get(
        "/api/tools/bank-journal/custom-fields", headers=auth_headers(user)
    )
    assert r.status_code == 200
    companies = {item["company_id"] for item in r.json()}
    assert {"co-A", "co-B"} <= companies


# ---------------------------------------------------------------------------
# A6. 审计日志收窄（NULL company 为平台级，scoped 用户不可见）
# ---------------------------------------------------------------------------


def _seed_audit(db, company_id):
    if company_id is not None:
        _ensure_company(db, company_id)
    aid = str(uuid4())
    db.add(
        AuditLog(
            id=aid,
            company_id=company_id,
            actor_id=None,
            action="test.event",
            entity_type="test",
            entity_id=aid,
        )
    )
    db.commit()
    return aid


def test_audit_logs_scoped_excludes_other_and_null(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    a_id = _seed_audit(db, "co-A")
    b_id = _seed_audit(db, "co-B")
    null_id = _seed_audit(db, None)
    # reviewer 拥有 AUDIT_VIEW 且非跨公司角色
    user = make_user(db, roles=["reviewer"], company_ids=["co-A"])
    r = c.get("/api/audit-logs", headers=auth_headers(user))
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert a_id in ids
    assert b_id not in ids
    assert null_id not in ids


def test_audit_logs_admin_sees_all(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    a_id = _seed_audit(db, "co-A")
    b_id = _seed_audit(db, "co-B")
    null_id = _seed_audit(db, None)
    user = make_user(db, roles=["admin"])
    r = c.get("/api/audit-logs", headers=auth_headers(user))
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert {a_id, b_id, null_id} <= ids


# ---------------------------------------------------------------------------
# B. 派生实体公司写校验（403）
# ---------------------------------------------------------------------------


def test_preview_row_patch_other_company_forbidden(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    run_id = _seed_run(db, "co-B")
    row_id = _seed_preview_row(db, run_id)
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.patch(
        f"/api/tools/bank-journal/preview-rows/{row_id}",
        json={
            "field_name": "amount",
            "new_value": "1",
            "reason": "x",
            "adjusted_by": user.id,
        },
        headers=auth_headers(user),
    )
    assert r.status_code == 403


def test_preview_row_confirm_other_company_forbidden(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    run_id = _seed_run(db, "co-B")
    row_id = _seed_preview_row(db, run_id)
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.post(
        f"/api/tools/bank-journal/preview-rows/{row_id}/confirm",
        json={"comment": "ok", "confirmed_by": user.id},
        headers=auth_headers(user),
    )
    assert r.status_code == 403


def test_preview_row_patch_missing_is_404(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.patch(
        "/api/tools/bank-journal/preview-rows/does-not-exist",
        json={
            "field_name": "amount",
            "new_value": "1",
            "reason": "x",
            "adjusted_by": user.id,
        },
        headers=auth_headers(user),
    )
    assert r.status_code == 404


def test_export_create_other_company_forbidden(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    run_id = _seed_run(db, "co-B")
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.post(
        f"/api/tools/bank-journal/conversion-runs/{run_id}/exports",
        json={"file_type": "csv", "columns": ["a"], "rows": [{"a": "1"}]},
        headers=auth_headers(user),
    )
    assert r.status_code == 403


def test_export_download_other_company_forbidden(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    run_id = _seed_run(db, "co-B")
    export_id = str(uuid4())
    db.add(
        Export(
            id=export_id,
            conversion_run_id=run_id,
            file_type="csv",
            storage_key=f"{export_id}.csv",
            row_count=0,
        )
    )
    db.commit()
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.get(
        f"/api/tools/bank-journal/exports/{export_id}/download",
        headers=auth_headers(user),
    )
    assert r.status_code == 403


def test_custom_field_patch_other_company_forbidden(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    field_id = _seed_custom_field(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.patch(
        f"/api/tools/bank-journal/custom-fields/{field_id}",
        json={"name": "new-name"},
        headers=auth_headers(user),
    )
    assert r.status_code == 403


def test_custom_field_delete_other_company_forbidden(
    client_with_db, make_user, auth_headers
):
    c, db = client_with_db
    field_id = _seed_custom_field(db, "co-B")
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.delete(
        f"/api/tools/bank-journal/custom-fields/{field_id}",
        headers=auth_headers(user),
    )
    assert r.status_code == 403
