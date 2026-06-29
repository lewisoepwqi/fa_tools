"""auth & rbac: user_roles/user_companies + 角色与管理员播种

Revision ID: 0005_auth_rbac
Revises: 0004_add_indexes
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.core.security import hash_password

revision = "0005_auth_rbac"
down_revision = "0004_add_indexes"
branch_labels = None
depends_on = None

_ROLES = [
    ("admin", "管理员"),
    ("template_admin", "模板管理员"),
    ("processor", "财务处理员"),
    ("reviewer", "财务复核员"),
    ("auditor", "审计查看员"),
]


def seed_roles_and_admin(conn, *, admin_email: str, admin_password: str) -> None:
    """幂等播种 5 角色 + 一个 admin 用户并绑定 admin 角色。

    可在任意 SQLAlchemy Connection 上调用，不依赖 Alembic op 上下文，
    因此可在单元/集成测试中直接使用。
    """
    # 播种角色：已存在则复用 id，不存在则插入
    role_ids: dict[str, str] = {}
    for code, name in _ROLES:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE code = :c"), {"c": code}
        ).first()
        if row:
            role_ids[code] = row[0]
        else:
            rid = str(uuid4())
            role_ids[code] = rid
            conn.execute(
                sa.text("INSERT INTO roles (id, code, name) VALUES (:id, :c, :n)"),
                {"id": rid, "c": code, "n": name},
            )

    # 播种引导管理员：已存在则直接返回
    admin_row = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :e"), {"e": admin_email}
    ).first()
    if admin_row:
        return

    uid = str(uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO users (id, email, name, password_hash, status) "
            "VALUES (:id, :e, :n, :p, 'active')"
        ),
        {"id": uid, "e": admin_email, "n": "管理员", "p": hash_password(admin_password)},
    )
    conn.execute(
        sa.text("INSERT INTO user_roles (user_id, role_id) VALUES (:u, :r)"),
        {"u": uid, "r": role_ids["admin"]},
    )


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), primary_key=True),
    )
    op.create_table(
        "user_companies",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "company_id", sa.String(36), sa.ForeignKey("companies.id"), primary_key=True
        ),
    )
    from app.core.config import get_settings  # 延迟导入，避免迁移模块被 import 时触发配置加载

    s = get_settings()
    seed_roles_and_admin(
        op.get_bind(),
        admin_email=s.bootstrap_admin_email,
        admin_password=s.bootstrap_admin_password,
    )


def downgrade() -> None:
    op.drop_table("user_companies")
    op.drop_table("user_roles")
