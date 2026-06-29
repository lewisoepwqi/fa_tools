"""Task 5: GET /api/companies 端点集成测试。

验证：
- 未鉴权请求返回 401
- admin（跨公司角色）可以看到所有公司
- 仅绑定特定公司的 processor 只能看到授权公司
"""

from app.models.company import Company


def _seed_companies(db, names: list[str]) -> list[Company]:
    """在测试 DB 中创建指定名称的公司，返回创建的公司列表。"""
    companies = []
    for name in names:
        comp = Company(id=f"test-co-{name}", name=name, status="active")
        db.add(comp)
        companies.append(comp)
    db.commit()
    return companies


def test_list_companies_requires_auth(client_with_db):
    """未带 token 请求应返回 401。"""
    c, _db = client_with_db
    resp = c.get("/api/companies")
    assert resp.status_code == 401


def test_admin_sees_all_companies(client_with_db, make_user, auth_headers):
    """admin（跨公司角色）应看到全部公司（含种子公司 + 新建公司）。"""
    c, db = client_with_db
    _seed_companies(db, ["Alpha", "Beta"])
    user = make_user(db, roles=["admin"])
    resp = c.get("/api/companies", headers=auth_headers(user))
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()}
    # 必须包含新建的两个公司（种子公司也在，但我们只断言新建的两个存在）
    assert {"Alpha", "Beta"} <= names


def test_processor_sees_only_accessible(client_with_db, make_user, auth_headers):
    """仅绑定 Alpha 公司的 processor 只能看到 Alpha，不能看到 Beta。"""
    c, db = client_with_db
    _seed_companies(db, ["Alpha", "Beta"])
    # processor 只绑定 Alpha 公司
    user = make_user(db, roles=["processor"], company_ids=["test-co-Alpha"])
    resp = c.get("/api/companies", headers=auth_headers(user))
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()}
    assert "Alpha" in names
    assert "Beta" not in names


def test_response_sorted_by_name(client_with_db, make_user, auth_headers):
    """响应应按 name 排序。"""
    c, db = client_with_db
    _seed_companies(db, ["Zebra", "Apple"])
    user = make_user(db, roles=["admin"])
    resp = c.get("/api/companies", headers=auth_headers(user))
    assert resp.status_code == 200
    all_names = [item["name"] for item in resp.json()]
    assert all_names == sorted(all_names)
