"""任务 15：租户隔离测试。

验证 conversion-runs 列表端点按可访问公司收窄：
- 仅绑定 co-A 的 processor 只能看到 co-A 的批次。
- admin（跨公司角色）可以看到所有批次。
"""

from uuid import uuid4

from app.models.company import Company
from app.tools.bank_journal.models.conversion import ConversionRun


def _seed_run(db, company_id):
    db.add(Company(id=company_id, name=company_id))
    run = ConversionRun(id=str(uuid4()), company_id=company_id, status="completed")
    db.add(run)
    db.commit()
    return run


def test_list_runs_scoped_to_accessible_company(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_run(db, "co-A")
    _seed_run(db, "co-B")
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.get(
        "/api/tools/bank-journal/conversion-runs", headers=auth_headers(user)
    )
    assert r.status_code == 200
    company_ids = {item["company_id"] for item in r.json()}
    assert company_ids == {"co-A"}


def test_admin_sees_all_companies(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    _seed_run(db, "co-A")
    _seed_run(db, "co-B")
    user = make_user(db, roles=["admin"])
    r = c.get(
        "/api/tools/bank-journal/conversion-runs", headers=auth_headers(user)
    )
    assert r.status_code == 200
    company_ids = {item["company_id"] for item in r.json()}
    assert company_ids == {"co-A", "co-B"}
