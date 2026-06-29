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


def test_me_admin_accessible_all(client_with_db, make_user):
    c, db = client_with_db
    user = make_user(db, roles=["admin"], email="a@x.com", password="pw")
    r = c.post("/api/auth/login", json={"email": "a@x.com", "password": "pw"})
    token = r.json()["access_token"]
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["accessible_companies"] == "all"
