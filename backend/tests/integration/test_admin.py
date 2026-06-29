"""管理端点集成测试。

覆盖场景：
- POST /api/admin/users 创建用户（含角色/公司绑定），新用户可登录
- GET /api/admin/users 列出所有用户（不含 password_hash）
- PUT /api/admin/users/{id}/roles 替换角色
- PUT /api/admin/users/{id}/companies 替换公司授权
- 非管理员访问管理端点返回 403
- 重复邮箱返回 409
- 未知角色/公司返回 422
"""

from app.models.company import Company


def test_admin_creates_user(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    db.add(Company(id="co-A", name="甲"))
    db.commit()
    admin = make_user(db, roles=["admin"])
    # 预先确保 processor 角色存在（管理端点要求角色必须是数据库已有记录）
    make_user(db, roles=["processor"])
    r = c.post(
        "/api/admin/users",
        headers=auth_headers(admin),
        json={
            "email": "new@x.com",
            "name": "新人",
            "password": "pw",
            "role_codes": ["processor"],
            "company_ids": ["co-A"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@x.com"
    assert "password_hash" not in body
    # 新用户可登录
    login = c.post("/api/auth/login", json={"email": "new@x.com", "password": "pw"})
    assert login.status_code == 200


def test_non_admin_cannot_manage_users(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"])
    r = c.get("/api/admin/users", headers=auth_headers(user))
    assert r.status_code == 403


def test_list_users_no_password_hash(client_with_db, make_user, auth_headers):
    """列表端点不得泄露 password_hash。"""
    c, db = client_with_db
    admin = make_user(db, roles=["admin"])
    r = c.get("/api/admin/users", headers=auth_headers(admin))
    assert r.status_code == 200
    users = r.json()
    for u in users:
        assert "password_hash" not in u


def test_duplicate_email_returns_409(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    admin = make_user(db, roles=["admin"])
    payload = {
        "email": "dup@x.com", "name": "X", "password": "pw",
        "role_codes": [], "company_ids": [],
    }
    r1 = c.post("/api/admin/users", headers=auth_headers(admin), json=payload)
    assert r1.status_code == 200
    r2 = c.post("/api/admin/users", headers=auth_headers(admin), json=payload)
    assert r2.status_code == 409


def test_unknown_role_returns_422(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    admin = make_user(db, roles=["admin"])
    r = c.post(
        "/api/admin/users",
        headers=auth_headers(admin),
        json={
            "email": "x@x.com", "name": "X", "password": "pw",
            "role_codes": ["nonexistent"], "company_ids": [],
        },
    )
    assert r.status_code == 422


def test_set_roles(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    admin = make_user(db, roles=["admin"])
    target = make_user(db, roles=["processor"])
    r = c.put(
        f"/api/admin/users/{target.id}/roles",
        headers=auth_headers(admin),
        json={"role_codes": ["admin"]},
    )
    assert r.status_code == 200
    assert "admin" in r.json()["roles"]


def test_set_roles_404_missing_user(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    admin = make_user(db, roles=["admin"])
    r = c.put(
        "/api/admin/users/nonexistent-id/roles",
        headers=auth_headers(admin),
        json={"role_codes": []},
    )
    assert r.status_code == 404


def test_set_companies(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    db.add(Company(id="co-B", name="乙"))
    db.commit()
    admin = make_user(db, roles=["admin"])
    target = make_user(db, roles=["processor"])
    r = c.put(
        f"/api/admin/users/{target.id}/companies",
        headers=auth_headers(admin),
        json={"company_ids": ["co-B"]},
    )
    assert r.status_code == 200
    assert "co-B" in r.json()["company_ids"]


def test_set_companies_404_missing_user(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    admin = make_user(db, roles=["admin"])
    r = c.put(
        "/api/admin/users/nonexistent-id/companies",
        headers=auth_headers(admin),
        json={"company_ids": []},
    )
    assert r.status_code == 404
