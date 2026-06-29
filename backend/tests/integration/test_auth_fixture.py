def test_make_user_and_headers(client_with_db, make_user, auth_headers):
    _, db = client_with_db
    user = make_user(db, roles=["admin"], email="x@y.com")
    headers = auth_headers(user)
    assert headers["Authorization"].startswith("Bearer ")
    assert user.email == "x@y.com"
    assert [r.code for r in user.roles] == ["admin"]
