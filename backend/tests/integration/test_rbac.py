import pytest
from fastapi import Depends

from app.api.deps import CurrentUserDep, require
from app.core.permissions import Permission
from app.main import app


@pytest.fixture(autouse=True)
def _probe_routes():
    @app.get("/__probe/me")
    def _me(user: CurrentUserDep):
        return {"id": user.id, "roles": user.roles}

    @app.get("/__probe/templates", dependencies=[Depends(require(Permission.TEMPLATE_MANAGE))])
    def _tpl():
        return {"ok": True}

    yield
    app.router.routes = [
        r for r in app.router.routes if not getattr(r, "path", "").startswith("/__probe")
    ]


def test_no_token_401(client_with_db):
    c, _ = client_with_db
    assert c.get("/__probe/me").status_code == 401


def test_valid_token_passes(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["admin"])
    r = c.get("/__probe/me", headers=auth_headers(user))
    assert r.status_code == 200
    assert r.json()["roles"] == ["admin"]


def test_permission_denied_403(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["auditor"])  # 无 TEMPLATE_MANAGE
    r = c.get("/__probe/templates", headers=auth_headers(user))
    assert r.status_code == 403


def test_permission_granted(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["template_admin"])
    r = c.get("/__probe/templates", headers=auth_headers(user))
    assert r.status_code == 200
