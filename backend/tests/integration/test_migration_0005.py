"""迁移 0005_auth_rbac 契约测试。

验证：
1. revision / down_revision 正确。
2. seed_roles_and_admin 在 SQLite 上幂等：两次调用后仍只有 5 角色 + 1 管理员。
"""
import importlib

from sqlalchemy import text


def test_revision_chain():
    mod = importlib.import_module("migrations.versions.0005_auth_rbac")
    assert mod.down_revision == "0004_add_indexes"
    assert mod.revision == "0005_auth_rbac"


def test_seed_roles_and_admin_idempotent(client_with_db):
    mod = importlib.import_module("migrations.versions.0005_auth_rbac")
    _, db = client_with_db
    conn = db.connection()
    mod.seed_roles_and_admin(conn, admin_email="root@x.com", admin_password="pw")
    mod.seed_roles_and_admin(conn, admin_email="root@x.com", admin_password="pw")
    roles = conn.execute(text("SELECT code FROM roles ORDER BY code")).scalars().all()
    assert set(roles) == {"admin", "auditor", "processor", "reviewer", "template_admin"}
    admins = conn.execute(
        text("SELECT email FROM users WHERE email = 'root@x.com'")
    ).scalars().all()
    assert admins == ["root@x.com"]  # 幂等：只一条
