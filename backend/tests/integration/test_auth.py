def test_login_success_and_me(client_with_db, make_user):
    c, db = client_with_db
    make_user(db, roles=["processor"], email="p@x.com", password="secret")
    r = c.post("/api/auth/login", json={"email": "p@x.com", "password": "secret"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "p@x.com"
    assert me.json()["roles"] == ["processor"]


def test_login_wrong_password_401(client_with_db, make_user):
    c, db = client_with_db
    make_user(db, roles=["processor"], email="p@x.com", password="secret")
    r = c.post("/api/auth/login", json={"email": "p@x.com", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user_401(client_with_db):
    c, _ = client_with_db
    r = c.post("/api/auth/login", json={"email": "ghost@x.com", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user_401(client_with_db, make_user):
    c, db = client_with_db
    # make_user 不支持 status= 参数，先建活跃用户再手动停用。
    from app.models.user import User

    usr = make_user(db, roles=["processor"], email="inactive@x.com", password="secret")
    db.query(User).filter(User.id == usr.id).update({"status": "inactive"})
    db.commit()
    r = c.post("/api/auth/login", json={"email": "inactive@x.com", "password": "secret"})
    assert r.status_code == 401


def test_me_admin_accessible_all(client_with_db, make_user):
    c, db = client_with_db
    make_user(db, roles=["admin"], email="a@x.com", password="pw")
    r = c.post("/api/auth/login", json={"email": "a@x.com", "password": "pw"})
    token = r.json()["access_token"]
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["accessible_companies"] == "all"
