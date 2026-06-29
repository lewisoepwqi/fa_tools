# W3 安全加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 FA Tools 平台补上安全底座:JWT 登录鉴权、五角色权限粒度 RBAC、按公司的租户隔离、敏感账号字段 Fernet 加密 + 展示脱敏、SQLite 外键约束生效、审计日志脱敏与补全,并提供前端完整 RBAC UI。

**Architecture:** 安全基础设施集中在平台共享层(`app/core` 纯函数模块 + `app/api/deps` 依赖 + `app/api/routes` 鉴权/管理端点),工具层路由只需挂权限依赖、用登录态替换 payload 自报身份。账号加密用 SQLAlchemy `TypeDecorator` 在模型层透明落地。前端用 `AuthProvider` + axios 拦截器 + 按权限渲染。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Pydantic v2、PyJWT、bcrypt、cryptography(Fernet);React 18 + TS + Ant Design v5 + axios。

依据 spec:`docs/superpowers/specs/2026-06-29-w3-security-hardening-design.md`。

## Global Constraints

- Python 3.12;ruff 规则 `E,F,I,UP,B`,行长 100。新增依赖:`PyJWT`、`bcrypt`、`cryptography`(加进 `backend/pyproject.toml` 并装入 `.venv`)。
- 后端命令:测试 `cd backend && .venv/bin/pytest -q`;单文件 `.venv/bin/pytest tests/...`;lint `cd backend && ruff check .`(ruff 在 `~/.local/bin`,不在 .venv)。
- `IdMixin.id` 是 `String(36)` 主键**无默认值**,插入时必须显式 `str(uuid4())`。
- 所有 `*_json` 列用通用 `JSON` 类型(SQLite 兼容)。
- 测试库:SQLite in-memory + `StaticPool` + override `get_db` + `Base.metadata.create_all`(见 `tests/conftest.py`)。新模型必须在 `tests/conftest.py` 顶部被 import 才会 create_all。
- Conventional commits,提交信息用中文。语言:注释/文档/提交用中文,技术术语保留原文。
- 角色 code 固定五个:`admin` / `template_admin` / `processor` / `reviewer` / `auditor`。
- 鉴权失败 → 401;有效身份但权限/公司越权 → 403。登录失败统一 401(不区分原因,防枚举)。
- 账号明文**永不出 API / 导出文件**;审计 json 不含明文敏感字段。

---

## 文件结构

**新建(后端):**
- `app/core/security.py` — 密码哈希 + JWT 签发/校验
- `app/core/crypto.py` — Fernet 加解密 + 账号掩码 + EncryptedString TypeDecorator
- `app/core/permissions.py` — Permission 枚举 + 角色→权限映射
- `app/models/associations.py` — `user_roles` / `user_companies` 关联表
- `app/api/routes/auth.py` — 登录、me
- `app/api/routes/admin.py` — 用户/角色/公司授权管理
- `app/schemas/auth.py` — 登录/me/admin 请求响应 schema
- `migrations/versions/0005_auth_rbac.py` — 关联表 + 角色/管理员播种
- 测试:`tests/unit/test_security.py`、`test_crypto.py`、`test_permissions.py`、`test_audit_redact.py`;`tests/integration/test_auth.py`、`test_rbac.py`、`test_tenant_isolation.py`、`test_admin.py`、`test_fk_pragma.py`、`test_field_encryption.py`

**修改(后端):**
- `app/core/config.py` — 新增 settings 字段
- `app/db/session.py` — SQLite FK pragma 监听
- `app/api/deps.py` — `CurrentUser` / `require` / `require_company_access` / `accessible_company_filter`
- `app/models/user.py` — User 关系(roles/companies)
- `app/services/audit_service.py` — redact + actor/ip/UA 补全
- `app/main.py` — 注册 auth/admin 路由
- `app/tools/bank_journal/models/conversion.py`、`app/models/company.py` — 两列改用 EncryptedString
- 各工具路由 + `app/api/routes/files.py`、`audit.py` — 挂权限依赖 + 去自报身份 + 租户过滤
- `tests/conftest.py` — auth fixtures + FK pragma 监听

**新建(前端):**
- `src/auth/AuthProvider.tsx`、`src/auth/useAuth.ts`、`src/auth/RequireAuth.tsx`
- `src/pages/LoginPage.tsx`
- `src/api/auth.ts`

**修改(前端):**
- `src/api/client.ts` — axios 拦截器
- `src/App.tsx`、`src/components/AppShell.tsx`、`src/tools/registry.ts` — 守卫 + 按权限菜单 + 公司切换器
- 各页面 — 去掉写死的 `user-1`/company,按权限显隐操作按钮

---

## Phase A — 核心纯函数模块

### Task 1: 密码哈希 + JWT(`core/security.py`)

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/unit/test_security.py`
- Modify: `backend/pyproject.toml`(加 `PyJWT`、`bcrypt` 依赖)

**Interfaces:**
- Produces:
  - `hash_password(plain: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
  - `create_access_token(*, user_id: str, roles: list[str], ttl_minutes: int, secret: str) -> str`
  - `decode_access_token(token: str, secret: str) -> dict`(返回含 `sub`/`roles`/`exp` 的 claims;过期或非法抛 `TokenError`)
  - `class TokenError(Exception)`

- [ ] **Step 1: 装依赖**

```bash
cd backend && .venv/bin/pip install "PyJWT>=2.8" "bcrypt>=4.1"
```
并在 `backend/pyproject.toml` 的 `dependencies` 数组加入 `"PyJWT>=2.8"`, `"bcrypt>=4.1"`。

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/unit/test_security.py
import time

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret"


def test_password_hash_roundtrip():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip_carries_claims():
    token = create_access_token(
        user_id="u1", roles=["admin"], ttl_minutes=60, secret=SECRET
    )
    claims = decode_access_token(token, SECRET)
    assert claims["sub"] == "u1"
    assert claims["roles"] == ["admin"]


def test_expired_token_raises():
    token = create_access_token(
        user_id="u1", roles=[], ttl_minutes=-1, secret=SECRET
    )
    with pytest.raises(TokenError):
        decode_access_token(token, SECRET)


def test_tampered_token_raises():
    token = create_access_token(
        user_id="u1", roles=[], ttl_minutes=60, secret=SECRET
    )
    with pytest.raises(TokenError):
        decode_access_token(token + "x", SECRET)


def test_wrong_secret_raises():
    token = create_access_token(
        user_id="u1", roles=[], ttl_minutes=60, secret=SECRET
    )
    with pytest.raises(TokenError):
        decode_access_token(token, "other-secret")
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_security.py -q`
Expected: FAIL(`ModuleNotFoundError: app.core.security`)

- [ ] **Step 4: 实现**

```python
# backend/app/core/security.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

_ALGO = "HS256"


class TokenError(Exception):
    """JWT 过期、签名错误或格式非法。"""


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *, user_id: str, roles: list[str], ttl_minutes: int, secret: str
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_ALGO)


def decode_access_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[_ALGO])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_security.py -q`
Expected: PASS(5 passed)

- [ ] **Step 6: 提交**

```bash
git add backend/app/core/security.py backend/tests/unit/test_security.py backend/pyproject.toml
git commit -m "feat(security): 密码 bcrypt 哈希 + JWT 签发/校验"
```

---

### Task 2: 字段加密 + 掩码(`core/crypto.py`)

**Files:**
- Create: `backend/app/core/crypto.py`
- Test: `backend/tests/unit/test_crypto.py`
- Modify: `backend/pyproject.toml`(加 `cryptography`)

**Interfaces:**
- Consumes: `app.core.config.get_settings`(读 `field_encryption_key`)
- Produces:
  - `encrypt(plain: str) -> str` / `decrypt(token: str) -> str`
  - `mask_account(value: str | None) -> str | None`(返回 `"****" + 后4位`,不足4位全掩 `"****"`,None → None)
  - `class EncryptedString(TypeDecorator)`(`impl = String`,bind 时加密、result 时解密;None 透传)

- [ ] **Step 1: 装依赖**

```bash
cd backend && .venv/bin/pip install "cryptography>=42"
```
并在 `backend/pyproject.toml` 的 `dependencies` 加 `"cryptography>=42"`。

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/unit/test_crypto.py
from app.core.crypto import decrypt, encrypt, mask_account


def test_encrypt_decrypt_roundtrip():
    cipher = encrypt("6222021234567890")
    assert cipher != "6222021234567890"
    assert decrypt(cipher) == "6222021234567890"


def test_encrypt_is_nondeterministic():
    assert encrypt("123456") != encrypt("123456")  # Fernet 随机 IV


def test_mask_account_keeps_last4():
    assert mask_account("6222021234567890") == "****7890"


def test_mask_account_short_value_all_masked():
    assert mask_account("12") == "****"


def test_mask_account_none():
    assert mask_account(None) is None
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_crypto.py -q`
Expected: FAIL(`ModuleNotFoundError: app.core.crypto`)

- [ ] **Step 4: 实现**

先在 `app/core/config.py` 的 `Settings` 加字段(Task 6 会统一补齐其余;此处先加 `field_encryption_key`):
```python
    # base64 url-safe 32B Fernet key;非 development 缺失则启动报错。开发用固定 key。
    field_encryption_key: str = "ZmFfdG9vbHNfZGV2X2tleV8zMmJ5dGVzX2xvbmdfISE="
```

```python
# backend/app/core/crypto.py
from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().field_encryption_key.encode("utf-8"))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def mask_account(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


class EncryptedString(TypeDecorator):
    """入库自动 Fernet 加密、读取自动解密的透明字符串列。None 透传。"""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt(value)
```

> 注:开发默认 key 是合法的 Fernet key(base64 url-safe 32B)。若测试报 `Invalid base64`,用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成一个替换默认值。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_crypto.py -q`
Expected: PASS(5 passed)

- [ ] **Step 6: 提交**

```bash
git add backend/app/core/crypto.py backend/tests/unit/test_crypto.py backend/app/core/config.py backend/pyproject.toml
git commit -m "feat(crypto): Fernet 字段加密 + 账号掩码 + EncryptedString 列类型"
```

---

### Task 3: 权限模型(`core/permissions.py`)

**Files:**
- Create: `backend/app/core/permissions.py`
- Test: `backend/tests/unit/test_permissions.py`

**Interfaces:**
- Produces:
  - `class Permission(StrEnum)`:`COMPANY_MANAGE USER_MANAGE TEMPLATE_MANAGE CONVERSION_PROCESS CONVERSION_CONFIRM EXPORT_RUN RULE_APPROVE AUDIT_VIEW READ`
  - `ROLE_PERMISSIONS: dict[str, set[Permission]]`(键为角色 code)
  - `permissions_for(roles: list[str]) -> set[Permission]`(并集;未知角色忽略)
  - `CROSS_COMPANY_ROLES: frozenset[str]` = `{"admin", "auditor"}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_permissions.py
from app.core.permissions import (
    CROSS_COMPANY_ROLES,
    ROLE_PERMISSIONS,
    Permission,
    permissions_for,
)


def test_all_five_roles_present():
    assert set(ROLE_PERMISSIONS) == {
        "admin",
        "template_admin",
        "processor",
        "reviewer",
        "auditor",
    }


def test_admin_has_all_permissions():
    assert ROLE_PERMISSIONS["admin"] == set(Permission)


def test_auditor_is_read_only():
    assert ROLE_PERMISSIONS["auditor"] == {Permission.READ, Permission.AUDIT_VIEW}


def test_permissions_for_unions_roles():
    perms = permissions_for(["processor", "auditor"])
    assert Permission.CONVERSION_PROCESS in perms
    assert Permission.AUDIT_VIEW in perms


def test_permissions_for_ignores_unknown_role():
    assert permissions_for(["nope"]) == set()


def test_cross_company_roles():
    assert CROSS_COMPANY_ROLES == frozenset({"admin", "auditor"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_permissions.py -q`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 实现**

```python
# backend/app/core/permissions.py
from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    COMPANY_MANAGE = "company_manage"
    USER_MANAGE = "user_manage"
    TEMPLATE_MANAGE = "template_manage"
    CONVERSION_PROCESS = "conversion_process"
    CONVERSION_CONFIRM = "conversion_confirm"
    EXPORT_RUN = "export_run"
    RULE_APPROVE = "rule_approve"
    AUDIT_VIEW = "audit_view"
    READ = "read"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "admin": set(Permission),
    "template_admin": {Permission.READ, Permission.TEMPLATE_MANAGE},
    "processor": {
        Permission.READ,
        Permission.CONVERSION_PROCESS,
        Permission.CONVERSION_CONFIRM,
        Permission.EXPORT_RUN,
    },
    "reviewer": {
        Permission.READ,
        Permission.CONVERSION_CONFIRM,
        Permission.RULE_APPROVE,
        Permission.AUDIT_VIEW,
    },
    "auditor": {Permission.READ, Permission.AUDIT_VIEW},
}

CROSS_COMPANY_ROLES: frozenset[str] = frozenset({"admin", "auditor"})


def permissions_for(roles: list[str]) -> set[Permission]:
    perms: set[Permission] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, set())
    return perms
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_permissions.py -q`
Expected: PASS(6 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/permissions.py backend/tests/unit/test_permissions.py
git commit -m "feat(permissions): 权限枚举 + 五角色→权限映射"
```

---

## Phase B — SQLite 外键 pragma

### Task 4: 开启 SQLite FK 约束

**Files:**
- Modify: `backend/app/db/session.py`
- Modify: `backend/tests/conftest.py`(测试 engine 挂同样监听)
- Test: `backend/tests/integration/test_fk_pragma.py`

**Interfaces:**
- Produces: 生产/测试 engine 在 SQLite 连接上自动执行 `PRAGMA foreign_keys=ON`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_fk_pragma.py
from sqlalchemy import text


def test_foreign_keys_pragma_on(client_with_db):
    _, db = client_with_db
    result = db.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_fk_pragma.py -q`
Expected: FAIL(`assert 0 == 1`)

- [ ] **Step 3: 实现 —— 生产 engine 监听**

在 `backend/app/db/session.py` 末尾(engine 定义之后)追加:
```python
from sqlalchemy import event  # 置于文件顶部 import 区


@event.listens_for(engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, connection_record) -> None:
    """SQLite 默认不强制外键约束,显式开启。对 PostgreSQL 无此回调影响。"""
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

- [ ] **Step 4: 实现 —— 测试 engine 监听**

在 `backend/tests/conftest.py` 的 `_create_test_engine` 改为挂监听:
```python
from sqlalchemy import create_engine, event  # 顶部 import 补 event


def _create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine
```

- [ ] **Step 5: 跑测试确认通过 + 全量回归**

Run: `cd backend && .venv/bin/pytest tests/integration/test_fk_pragma.py -q`
Expected: PASS
Run: `cd backend && .venv/bin/pytest -q`
Expected: 全绿。**若有测试因悬挂外键新失败,逐个修复(插入前先建父行,或修正 fixture);这是 FK 开启暴露的真问题。** 修复后再提交。

- [ ] **Step 6: 提交**

```bash
git add backend/app/db/session.py backend/tests/conftest.py backend/tests/integration/test_fk_pragma.py
git commit -m "feat(db): SQLite 连接开启 PRAGMA foreign_keys=ON"
```

---

## Phase C — 模型、配置、迁移、测试夹具

### Task 5: 关联表 user_roles / user_companies + User 关系

**Files:**
- Create: `backend/app/models/associations.py`
- Modify: `backend/app/models/user.py`(加 relationships)
- Modify: `backend/app/models/__init__.py`(import 新模型)
- Modify: `backend/tests/conftest.py`(顶部 import associations,确保 create_all 建表)
- Test: `backend/tests/integration/test_user_associations.py`

**Interfaces:**
- Produces:
  - `UserRole`(`user_id` FK users.id PK 复合, `role_id` FK roles.id PK 复合)
  - `UserCompany`(`user_id` FK users.id, `company_id` FK companies.id,复合 PK)
  - `User.roles: list[Role]`、`User.companies: list[Company]`(SQLAlchemy relationship,secondary 关联表)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_user_associations.py
from uuid import uuid4

from app.models.company import Company
from app.models.user import Role, User


def test_user_role_and_company_relationships(client_with_db):
    _, db = client_with_db
    user = User(id=str(uuid4()), email="a@x.com", password_hash="h")
    role = Role(id=str(uuid4()), code="processor", name="财务处理员")
    company = Company(id=str(uuid4()), name="甲公司")
    user.roles.append(role)
    user.companies.append(company)
    db.add_all([user, role, company])
    db.commit()
    db.refresh(user)
    assert [r.code for r in user.roles] == ["processor"]
    assert [c.name for c in user.companies] == ["甲公司"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_user_associations.py -q`
Expected: FAIL(`AttributeError: 'User' object has no attribute 'roles'`)

- [ ] **Step 3: 实现关联表**

```python
# backend/app/models/associations.py
from sqlalchemy import Column, ForeignKey, Table

from app.db.base import Base

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

user_companies = Table(
    "user_companies",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("company_id", ForeignKey("companies.id"), primary_key=True),
)
```

- [ ] **Step 4: User 加 relationships**

在 `backend/app/models/user.py` 的 `User` 类内补(并在顶部 `from sqlalchemy.orm import Mapped, mapped_column, relationship`,import `associations`):
```python
from app.models.associations import user_companies, user_roles
from app.models.company import Company  # 若产生循环 import,用字符串形式 relationship("Company")

# User 类体内:
    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=user_roles, lazy="selectin"
    )
    companies: Mapped[list[Company]] = relationship(
        "Company", secondary=user_companies, lazy="selectin"
    )
```
> 循环 import 风险:`company.py` 不 import `user.py`,故在 `user.py` import `Company` 安全。若 ruff/运行报循环,改用字符串目标 `relationship("Company", secondary=user_companies, lazy="selectin")` 并删除 Company import。

- [ ] **Step 5: 注册到 metadata + conftest import**

`backend/app/models/__init__.py` 加 `from app.models import associations  # noqa: F401`(若该文件以 import 触发注册的方式组织,照其现有风格添加)。
`backend/tests/conftest.py` 第 15 行附近改为:
```python
from app.models import associations, audit, company, file, user  # noqa: F401
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_user_associations.py -q`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/associations.py backend/app/models/user.py backend/app/models/__init__.py backend/tests/conftest.py backend/tests/integration/test_user_associations.py
git commit -m "feat(models): user_roles/user_companies 关联表 + User 关系"
```

---

### Task 6: 配置项补齐(`core/config.py`)

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_config.py`

**Interfaces:**
- Produces(`Settings` 新增):
  - `access_token_ttl_minutes: int = 480`
  - `field_encryption_key: str`(Task 2 已加)
  - `bootstrap_admin_email: str = "admin@example.com"`
  - `bootstrap_admin_password: str = "changeme"`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_config.py
from app.core.config import Settings


def test_security_settings_defaults():
    s = Settings()
    assert s.access_token_ttl_minutes == 480
    assert s.bootstrap_admin_email
    assert s.bootstrap_admin_password
    assert s.field_encryption_key
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_config.py -q`
Expected: FAIL(`AttributeError: access_token_ttl_minutes`)

- [ ] **Step 3: 实现**

在 `backend/app/core/config.py` 的 `Settings` 加:
```python
    access_token_ttl_minutes: int = 480
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "changeme"
```
(`field_encryption_key` 在 Task 2 已加;若未加则一并补上。)

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_config.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): 新增 token ttl / 加密密钥 / 引导管理员配置"
```

---

### Task 7: Alembic 迁移 0005(关联表 + 角色/管理员播种)

**Files:**
- Create: `backend/migrations/versions/0005_auth_rbac.py`
- Modify: `backend/migrations/env.py`(确认 import 了关联表所属模块;若已 import app.models.* 则无需改)
- Test: `backend/tests/integration/test_migration_0005.py`(契约测:create_all 后角色表可被代码播种逻辑使用 —— 见说明)

> 说明:本环境无 Docker/PG,迁移不在 PG 实跑。测试只验证 `upgrade` 函数可被 import 且 `down_revision == "0004_add_indexes"`,并验证一个可复用的纯播种函数 `seed_roles_and_admin(connection)` 行为(在 SQLite 上跑)。

**Interfaces:**
- Produces:
  - 迁移 `revision = "0005_auth_rbac"`,`down_revision = "0004_add_indexes"`
  - 一个可单测的纯函数 `seed_roles_and_admin(conn, *, admin_email, admin_password)`:插入缺失的 5 角色 + 一个 admin 用户 + user_roles 绑定(幂等:已存在则跳过)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_migration_0005.py
import importlib

from sqlalchemy import text


def test_revision_chain():
    mod = importlib.import_module("migrations.versions.0005_auth_rbac")
    assert mod.down_revision == "0004_add_indexes"
    assert mod.revision == "0005_auth_rbac"


def test_seed_roles_and_admin_idempotent(client_with_db):
    from migrations.versions import importlib as _  # noqa
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
    assert admins == ["root@x.com"]  # 幂等:只一条
```

> 注:`migrations.versions.0005_auth_rbac` 模块名以数字开头不能直接 `import`,用 `importlib.import_module` 字符串导入(如上)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_migration_0005.py -q`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: 实现迁移**

```python
# backend/migrations/versions/0005_auth_rbac.py
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
    """幂等播种 5 角色 + 一个 admin 用户并绑定 admin 角色。"""
    existing = set(
        conn.execute(sa.text("SELECT code FROM roles")).scalars().all()
    )
    role_ids: dict[str, str] = {}
    for code, name in _ROLES:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE code = :c"), {"c": code}
        ).first()
        if row:
            role_ids[code] = row[0]
            continue
        rid = str(uuid4())
        role_ids[code] = rid
        conn.execute(
            sa.text("INSERT INTO roles (id, code, name) VALUES (:id, :c, :n)"),
            {"id": rid, "c": code, "n": name},
        )
    _ = existing
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
        sa.text(
            "INSERT INTO user_roles (user_id, role_id) VALUES (:u, :r)"
        ),
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
    from app.core.config import get_settings

    s = get_settings()
    seed_roles_and_admin(
        op.get_bind(),
        admin_email=s.bootstrap_admin_email,
        admin_password=s.bootstrap_admin_password,
    )


def downgrade() -> None:
    op.drop_table("user_companies")
    op.drop_table("user_roles")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_migration_0005.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/migrations/versions/0005_auth_rbac.py backend/tests/integration/test_migration_0005.py
git commit -m "feat(migration): 0005 关联表 + 角色/引导管理员幂等播种"
```

---

### Task 8: 测试鉴权夹具(conftest)

**Files:**
- Modify: `backend/tests/conftest.py`
- Test:(夹具本身在 Task 9/10 被消费验证;此任务加一个自检测试 `tests/integration/test_auth_fixture.py`)

**Interfaces:**
- Produces(pytest fixtures):
  - `make_user`(factory):`make_user(db, *, roles: list[str], company_ids: list[str] = (), email=...) -> User`(创建用户 + 角色 + 公司授权,角色按 code 查/建)
  - `auth_headers`(factory):`auth_headers(user) -> dict`(返回 `{"Authorization": f"Bearer {token}"}`,token 用 `create_access_token` + settings)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_auth_fixture.py
def test_make_user_and_headers(client_with_db, make_user, auth_headers):
    _, db = client_with_db
    user = make_user(db, roles=["admin"], email="x@y.com")
    headers = auth_headers(user)
    assert headers["Authorization"].startswith("Bearer ")
    assert user.email == "x@y.com"
    assert [r.code for r in user.roles] == ["admin"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_auth_fixture.py -q`
Expected: FAIL(`fixture 'make_user' not found`)

- [ ] **Step 3: 实现夹具**

在 `backend/tests/conftest.py` 追加:
```python
from uuid import uuid4

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.company import Company
from app.models.user import Role, User


@pytest.fixture
def make_user():
    def _make(db, *, roles, company_ids=(), email=None, password="pw"):
        user = User(
            id=str(uuid4()),
            email=email or f"u{uuid4().hex[:8]}@x.com",
            password_hash=hash_password(password),
            status="active",
        )
        for code in roles:
            role = db.query(Role).filter(Role.code == code).first()
            if role is None:
                role = Role(id=str(uuid4()), code=code, name=code)
                db.add(role)
            user.roles.append(role)
        for cid in company_ids:
            company = db.get(Company, cid)
            if company is None:
                company = Company(id=cid, name=cid)
                db.add(company)
            user.companies.append(company)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_headers():
    settings = get_settings()

    def _headers(user):
        token = create_access_token(
            user_id=user.id,
            roles=[r.code for r in user.roles],
            ttl_minutes=settings.access_token_ttl_minutes,
            secret=settings.secret_key,
        )
        return {"Authorization": f"Bearer {token}"}

    return _headers
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_auth_fixture.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/tests/conftest.py backend/tests/integration/test_auth_fixture.py
git commit -m "test: 新增 make_user / auth_headers 鉴权夹具"
```

---

## Phase D — 鉴权依赖与端点

### Task 9: 鉴权依赖(`api/deps.py`)

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/integration/test_rbac.py`(本任务用一个临时受保护探针路由测 401/403/放行)

**Interfaces:**
- Produces:
  - `class CurrentUser`(dataclass/pydantic):`id: str`、`roles: list[str]`、`permissions: set[Permission]`、`accessible_company_ids: set[str] | None`(None = 全公司)
  - `get_current_user(db, authorization: str | None) -> CurrentUser`(401 缺/坏 token 或用户停用)
  - `CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]`
  - `require(*perms: Permission)`(返回校验依赖,缺权限 403)
  - `require_company_access(user: CurrentUser, company_id: str | None) -> None`(越权 403;company_id None 时仅校验需带公司的语义由调用方决定)
  - `accessible_company_filter(user: CurrentUser) -> set[str] | None`(None=不收窄)

- [ ] **Step 1: 写失败测试(含临时探针路由)**

```python
# backend/tests/integration/test_rbac.py
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_rbac.py -q`
Expected: FAIL(`ImportError: CurrentUserDep`)

- [ ] **Step 3: 实现 deps**

```python
# backend/app/api/deps.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import (
    CROSS_COMPANY_ROLES,
    Permission,
    permissions_for,
)
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


@dataclass
class CurrentUser:
    id: str
    roles: list[str]
    permissions: set[Permission]
    accessible_company_ids: set[str] | None  # None = 全公司(跨公司角色)


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未认证")
    token = authorization.split(" ", 1)[1]
    try:
        claims = decode_access_token(token, get_settings().secret_key)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌无效") from exc
    user = db.get(User, claims.get("sub"))
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不可用")
    roles = [r.code for r in user.roles]
    cross = any(r in CROSS_COMPANY_ROLES for r in roles)
    accessible = None if cross else {c.id for c in user.companies}
    return CurrentUser(
        id=user.id,
        roles=roles,
        permissions=permissions_for(roles),
        accessible_company_ids=accessible,
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require(*perms: Permission):
    def _checker(user: CurrentUserDep) -> CurrentUser:
        if not set(perms).issubset(user.permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")
        return user

    return _checker


def require_company_access(user: CurrentUser, company_id: str | None) -> None:
    if user.accessible_company_ids is None:
        return  # 跨公司角色
    if company_id is None or company_id not in user.accessible_company_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该公司数据")


def accessible_company_filter(user: CurrentUser) -> set[str] | None:
    return user.accessible_company_ids
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_rbac.py -q`
Expected: PASS(4 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/deps.py backend/tests/integration/test_rbac.py
git commit -m "feat(deps): CurrentUser + require 权限 + 公司访问校验依赖"
```

---

### Task 10: 登录 + me 端点(`api/routes/auth.py`)

**Files:**
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/schemas/auth.py`
- Modify: `backend/app/main.py`(注册 auth 路由)
- Test: `backend/tests/integration/test_auth.py`

**Interfaces:**
- Consumes: `security.verify_password/create_access_token`、`CurrentUserDep`、`record_audit_event`
- Produces:
  - `POST /api/auth/login` `{email, password}` → `{access_token, token_type}`(失败 401)
  - `GET /api/auth/me` → `{id, email, name, roles, accessible_companies}`(`accessible_companies` 为 `"all"` 或 `[{id,name}]`)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_auth.py
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_auth.py -q`
Expected: FAIL(404 —— 路由不存在)

- [ ] **Step 3: 实现 schema**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CompanyRef(BaseModel):
    id: str
    name: str


class MeResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    roles: list[str]
    accessible_companies: list[CompanyRef] | str  # "all" 或公司列表
```

- [ ] **Step 4: 实现路由**

```python
# backend/app/api/routes/auth.py
from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUserDep, DbSession
from app.core.config import get_settings
from app.core.permissions import CROSS_COMPANY_ROLES
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import CompanyRef, LoginRequest, MeResponse, TokenResponse
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(db: DbSession, payload: LoginRequest, request: Request) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    ok = user is not None and user.status == "active" and verify_password(
        payload.password, user.password_hash
    )
    if not ok:
        record_audit_event(
            db,
            company_id=None,
            actor_id=user.id if user else None,
            action="login",
            entity_type="user",
            entity_id=user.id if user else "unknown",
            after={"success": False},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    settings = get_settings()
    token = create_access_token(
        user_id=user.id,
        roles=[r.code for r in user.roles],
        ttl_minutes=settings.access_token_ttl_minutes,
        secret=settings.secret_key,
    )
    record_audit_event(
        db,
        company_id=None,
        actor_id=user.id,
        action="login",
        entity_type="user",
        entity_id=user.id,
        after={"success": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(db: DbSession, user: CurrentUserDep) -> MeResponse:
    db_user = db.get(User, user.id)
    cross = any(r in CROSS_COMPANY_ROLES for r in user.roles)
    companies: list[CompanyRef] | str
    if cross:
        companies = "all"
    else:
        companies = [CompanyRef(id=c.id, name=c.name) for c in db_user.companies]
    return MeResponse(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        roles=user.roles,
        accessible_companies=companies,
    )
```

- [ ] **Step 5: 注册路由**

`backend/app/main.py`:`from app.api.routes import audit, auth, files` 并 `app.include_router(auth.router)`。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_auth.py -q`
Expected: PASS(4 passed)

- [ ] **Step 7: 提交**

```bash
git add backend/app/api/routes/auth.py backend/app/schemas/auth.py backend/app/main.py backend/tests/integration/test_auth.py
git commit -m "feat(auth): 登录签发 JWT + /me + 登录审计"
```

---

## Phase E — 字段加密接入

### Task 11: 两列改用 EncryptedString

**Files:**
- Modify: `backend/app/models/company.py:account_no_encrypted`
- Modify: `backend/app/tools/bank_journal/models/conversion.py:counterparty_account_no_encrypted`
- Test: `backend/tests/integration/test_field_encryption.py`

**Interfaces:**
- Consumes: `app.core.crypto.EncryptedString`
- Produces: 两列入库密文、读取明文。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_field_encryption.py
from uuid import uuid4

from sqlalchemy import text

from app.models.company import BankAccount, Company


def test_account_no_encrypted_at_rest(client_with_db):
    _, db = client_with_db
    company = Company(id=str(uuid4()), name="甲")
    acct = BankAccount(
        id=str(uuid4()),
        company_id=company.id,
        bank_name="工行",
        account_name="甲账户",
        account_no_encrypted="6222021234567890",
    )
    db.add_all([company, acct])
    db.commit()
    # ORM 读取 → 明文
    db.refresh(acct)
    assert acct.account_no_encrypted == "6222021234567890"
    # 原始 SQL 读取 → 密文(非明文)
    raw = db.execute(
        text("SELECT account_no_encrypted FROM bank_accounts WHERE id = :i"),
        {"i": acct.id},
    ).scalar()
    assert raw != "6222021234567890"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_field_encryption.py -q`
Expected: FAIL(`assert '6222...' != '6222...'` —— 明文落库)

- [ ] **Step 3: 实现**

`backend/app/models/company.py`:import `from app.core.crypto import EncryptedString`,把
```python
    account_no_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
```
改为
```python
    account_no_encrypted: Mapped[str] = mapped_column(EncryptedString(512), nullable=False)
```
`backend/app/tools/bank_journal/models/conversion.py`:同样 import,把
```python
    counterparty_account_no_encrypted: Mapped[str | None] = mapped_column(String(512))
```
改为
```python
    counterparty_account_no_encrypted: Mapped[str | None] = mapped_column(EncryptedString(512))
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest tests/integration/test_field_encryption.py -q`
Expected: PASS
Run: `cd backend && .venv/bin/pytest -q`
Expected: 全绿(注意 conversion 相关测试若写入该列,现在仍透明工作)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/company.py backend/app/tools/bank_journal/models/conversion.py backend/tests/integration/test_field_encryption.py
git commit -m "feat(crypto): 银行账号/对手账号列改 EncryptedString 透明加密"
```

---

### Task 12: 账号展示脱敏

**Files:**
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(预览/详情响应里对手账号字段用 `mask_account`)
- Modify: `backend/app/tools/bank_journal/services/export_service.py`(导出对手账号列用 `mask_account`)
- Test: `backend/tests/unit/test_account_masking.py`(纯函数级,验证响应/导出构造处掩码)

> 说明:先 grep 定位 `counterparty_account_no` 在响应/导出 schema 的出处:
> `grep -rn "counterparty_account_no" backend/app/tools/bank_journal --include=*.py | grep -v __pycache__`。
> 对每个把该字段放进 API 响应或导出行的位置,套 `mask_account(...)`。若该字段当前未进任何响应/导出,
> 本任务仅新增一个针对 `mask_account` 在 service 装配函数上的单测占位并记录"当前无暴露点",不强行造暴露。

**Interfaces:**
- Consumes: `app.core.crypto.mask_account`

- [ ] **Step 1: 定位暴露点**

Run: `grep -rn "counterparty_account_no" backend/app/tools/bank_journal --include=*.py | grep -v __pycache__`
记录哪些函数把它放进响应/导出。

- [ ] **Step 2: 写失败测试(针对定位到的装配函数)**

示例(若 `build_preview_row` 或预览响应装配把对手账号放进 `output_values` / 响应):
```python
# backend/tests/unit/test_account_masking.py
from app.core.crypto import mask_account


def test_mask_account_in_response_helper():
    # 占位:验证掩码函数对账号生效;实际断言应针对定位到的响应/导出装配函数,
    # 例如 assert response.counterparty_account_no == "****7890"
    assert mask_account("6222021234567890") == "****7890"
```
> 实施者:把占位替换为针对 Step 1 定位到的真实装配函数的断言(传明文对手账号,断言响应/导出行里是掩码)。

- [ ] **Step 3: 跑测试确认失败 / 实现掩码**

在定位到的每个装配点,对对手账号字段调用 `mask_account(...)` 后再放入响应/导出行。
若 Step 1 发现确无暴露点,跳过实现,仅保留占位测试并在提交信息注明。

- [ ] **Step 4: 跑测试 + 回归**

Run: `cd backend && .venv/bin/pytest tests/unit/test_account_masking.py -q && cd backend && .venv/bin/pytest -q`
Expected: 全绿

- [ ] **Step 5: 提交**

```bash
git add backend/app/tools/bank_journal/services/ backend/tests/unit/test_account_masking.py
git commit -m "feat(crypto): 对手账号在响应/导出中展示脱敏"
```

---

## Phase F — 审计脱敏与补全

### Task 13: 审计 redact 脱敏

**Files:**
- Modify: `backend/app/services/audit_service.py`
- Test: `backend/tests/unit/test_audit_redact.py`

**Interfaces:**
- Produces:
  - `redact(payload: dict | None) -> dict | None`(纯函数:敏感键脱敏。账号类键 → 掩码;密钥/口令/token 类键 → `"***"`)
  - `build_audit_event` / `record_audit_event` 在写 before/after 前对其调用 `redact`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_audit_redact.py
from app.services.audit_service import redact


def test_redact_password_and_token():
    out = redact({"password_hash": "abc", "access_token": "t", "name": "甲"})
    assert out["password_hash"] == "***"
    assert out["access_token"] == "***"
    assert out["name"] == "甲"


def test_redact_account_masked():
    out = redact({"account_no_encrypted": "6222021234567890"})
    assert out["account_no_encrypted"] == "****7890"


def test_redact_nested():
    out = redact({"inner": {"password": "p", "x": 1}})
    assert out["inner"]["password"] == "***"
    assert out["inner"]["x"] == 1


def test_redact_none():
    assert redact(None) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_audit_redact.py -q`
Expected: FAIL(`ImportError: redact`)

- [ ] **Step 3: 实现**

在 `backend/app/services/audit_service.py` 顶部加:
```python
from app.core.crypto import mask_account

_SECRET_KEYS = {"password", "password_hash", "token", "access_token", "field_encryption_key", "secret_key"}
_ACCOUNT_KEY_HINT = "account_no"


def redact(payload: dict | None) -> dict | None:
    if payload is None:
        return None

    def _walk(value):
        if isinstance(value, dict):
            out = {}
            for k, v in value.items():
                lk = str(k).lower()
                if lk in _SECRET_KEYS:
                    out[k] = "***"
                elif _ACCOUNT_KEY_HINT in lk and isinstance(v, str):
                    out[k] = mask_account(v)
                else:
                    out[k] = _walk(v)
            return out
        if isinstance(value, (list, tuple)):
            return [_walk(i) for i in value]
        return value

    return _walk(payload)
```
并在 `build_audit_event` 里改:
```python
        "before_json": _json_safe(redact(before)),
        "after_json": _json_safe(redact(after)),
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest tests/unit/test_audit_redact.py -q && cd backend && .venv/bin/pytest -q`
Expected: 全绿

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/audit_service.py backend/tests/unit/test_audit_redact.py
git commit -m "feat(audit): before/after 快照敏感字段脱敏(redact)"
```

---

### Task 14: 审计补全 actor / ip / UA

**Files:**
- Modify: `backend/app/services/audit_service.py`(已有 ip/ua 参数,确认透传)
- Modify: `backend/app/api/routes/files.py`、`backend/app/api/routes/audit.py` 及工具路由 —— 在 Task 16 统一处理 actor/ip/ua。本任务仅补一个 helper。
- Test: `backend/tests/unit/test_audit_request_ctx.py`

**Interfaces:**
- Produces: `audit_ctx(request: Request) -> dict`(返回 `{"ip_address": ..., "user_agent": ...}`,供路由 `**audit_ctx(request)` 传入 `record_audit_event`)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_audit_request_ctx.py
from app.services.audit_service import audit_ctx


class _FakeReq:
    class client:
        host = "1.2.3.4"
    headers = {"user-agent": "pytest"}


def test_audit_ctx_extracts():
    ctx = audit_ctx(_FakeReq())
    assert ctx == {"ip_address": "1.2.3.4", "user_agent": "pytest"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_audit_request_ctx.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/services/audit_service.py` 加:
```python
def audit_ctx(request) -> dict:
    client = getattr(request, "client", None)
    return {
        "ip_address": getattr(client, "host", None) if client else None,
        "user_agent": request.headers.get("user-agent"),
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_audit_request_ctx.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/audit_service.py backend/tests/unit/test_audit_request_ctx.py
git commit -m "feat(audit): audit_ctx 提取请求 ip/user-agent"
```

---

## Phase G — 给路由挂 RBAC + 租户 + 去自报身份

### Task 15: 租户过滤 helper + 列表端点收窄

**Files:**
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(`list_conversion_runs` 加可选 `accessible: set[str] | None`)
- Modify: `backend/app/api/routes/audit.py`(列表按 accessible 过滤)
- Test: `backend/tests/integration/test_tenant_isolation.py`

**Interfaces:**
- Consumes: `accessible_company_filter`、`CurrentUserDep`
- Produces: list 端点对非跨公司用户仅返回其授权公司的数据。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_tenant_isolation.py
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
    company_ids = {item["company_id"] for item in r.json()}
    assert company_ids == {"co-A", "co-B"}
```
> 注:`ConversionRun` 必填列若不止 `status`,按其模型补齐最小字段(参考 `models/conversion.py`)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_tenant_isolation.py -q`
Expected: FAIL(401,因端点尚未挂鉴权;或返回全部)

- [ ] **Step 3: 实现 service 收窄**

`list_conversion_runs(db, company_id=None, accessible=None)`:在查询后加
```python
    if accessible is not None:
        query = query.filter(ConversionRun.company_id.in_(accessible))
```
(`accessible` 为空集合时应返回空 —— `in_([])` 即空结果,符合预期。)

- [ ] **Step 4: 路由接线(本端点)**

`conversion_runs.py` 的 `list_runs` 改为:
```python
from app.api.deps import CurrentUserDep, DbSession, accessible_company_filter
from app.core.permissions import Permission
from fastapi import Depends


@router.get("", response_model=list[ConversionRunListItemResponse],
            dependencies=[Depends(require(Permission.READ))])
def list_runs(
    db: DbSession, user: CurrentUserDep, company_id: str | None = None
) -> list[ConversionRunListItemResponse]:
    return list_conversion_runs(db, company_id, accessible_company_filter(user))
```
(`require`、`accessible_company_filter` 从 deps import。)

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/integration/test_tenant_isolation.py -q`
Expected: PASS(2 passed)

- [ ] **Step 6: 提交**

```bash
git add backend/app/tools/bank_journal/services/conversion_service.py backend/app/tools/bank_journal/routes/conversion_runs.py backend/tests/integration/test_tenant_isolation.py
git commit -m "feat(tenant): conversion-runs 列表按可访问公司收窄"
```

---

### Task 16: 全路由挂权限依赖 + 去自报身份 + 公司校验

**Files:**(逐个修改 —— 同一机械模式)
- `backend/app/api/routes/files.py`、`audit.py`
- `backend/app/tools/bank_journal/routes/`:`bank_templates.py`、`journal_templates.py`、`mapping_profiles.py`、`rules.py`、`conversion_runs.py`、`preview_rows.py`、`exports.py`、`custom_fields.py`
- Test: `backend/tests/integration/test_route_guards.py` + 全量回归(已有集成测需补 `auth_headers`)

**权限映射(端点 → require):**
- 上传/发起转换/from-config/dry-run/preview-row PATCH → `CONVERSION_PROCESS`
- preview-row confirm → `CONVERSION_CONFIRM`
- exports 创建/download → `EXPORT_RUN`
- 模板/映射/规则/custom_fields 的 POST/新建 → `TEMPLATE_MANAGE`
- 所有 GET 列表/详情 → `READ`
- audit-logs 列表 → `AUDIT_VIEW`

**Interfaces:**
- Consumes: `CurrentUserDep`、`require(Permission.X)`、`require_company_access`、`audit_ctx`、`accessible_company_filter`
- 每个写端点:
  1. 路由签名加 `user: CurrentUserDep`(或 `dependencies=[Depends(require(...))]`)。
  2. 删除 payload/Form 里的 `user_id`/`uploaded_by`/`actor` 自报字段;`actor_id` 改 `user.id`。
  3. 凡 payload 带 `company_id`:调 `require_company_access(user, payload.company_id)`。
  4. `record_audit_event(... actor_id=user.id, **audit_ctx(request))`(路由签名加 `request: Request`)。
  5. list 端点:传 `accessible_company_filter(user)` 给 service(service 加该可选形参并 `.in_()` 过滤,模式同 Task 15)。

- [ ] **Step 1: 写守卫测试(代表性端点)**

```python
# backend/tests/integration/test_route_guards.py
def test_upload_requires_auth(client_with_db):
    c, _ = client_with_db
    r = c.post("/api/files/upload", data={"company_id": "co-A"})
    assert r.status_code == 401


def test_audit_requires_audit_view(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"])  # 无 AUDIT_VIEW
    r = c.get("/api/audit-logs", headers=auth_headers(user))
    assert r.status_code == 403


def test_template_create_denied_for_processor(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.post(
        "/api/tools/bank-journal/bank-templates",
        headers=auth_headers(user),
        json={"company_id": "co-A", "name": "t", "parse_config": {}},
    )
    assert r.status_code == 403


def test_cross_company_write_denied(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["template_admin"], company_ids=["co-A"])
    r = c.post(
        "/api/tools/bank-journal/bank-templates",
        headers=auth_headers(user),
        json={"company_id": "co-B", "name": "t", "parse_config": {}},
    )
    assert r.status_code == 403
```
> 注:body 形状以各端点真实 schema 为准(此处仅示意);若 schema 必填字段更多,补齐到能过 422、卡在 403。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_route_guards.py -q`
Expected: FAIL(当前端点无鉴权 → 200/422 而非 401/403)

- [ ] **Step 3: 逐路由改造**

对上表每个路由文件,按 Interfaces 的 5 步机械改造。示例(`files.py` upload):
```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentUserDep, DbSession, require, require_company_access
from app.core.permissions import Permission
from app.services.audit_service import audit_ctx, record_audit_event


@router.post("/upload", response_model=UploadedFileResponse,
             dependencies=[Depends(require(Permission.CONVERSION_PROCESS))])
async def upload_file(
    db: DbSession,
    user: CurrentUserDep,
    request: Request,
    company_id: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008
) -> UploadedFileResponse:
    require_company_access(user, company_id)
    content = await file.read()
    ...  # 落库逻辑不变,uploaded_by 改 user.id
    response = UploadedFileResponse(company_id=company_id, uploaded_by=user.id, **saved)
    record_audit_event(
        db, company_id=company_id, actor_id=user.id,
        action="file.uploaded", entity_type="source_file", entity_id=source_file.id,
        after=response.model_dump(), **audit_ctx(request),
    )
    return response
```
> `UploadedFileResponse` 若必填 `uploaded_by`,保留字段但值取 `user.id`。`SourceFile.uploaded_by` 同理。
> 其余路由按各自 `record_audit_event` 调用处替换 `actor_id=None` → `actor_id=user.id`,加 `**audit_ctx(request)`,
> 写端点加 `require_company_access(user, payload.company_id)`,挂 `dependencies=[Depends(require(<对应权限>))]`。

- [ ] **Step 4: 修复既有集成测(补 auth_headers)**

现有 `tests/integration/` 里所有调用受保护端点的测试现在会 401。逐个补 `headers=auth_headers(user)`,
其中 `user = make_user(db, roles=[<能过该端点权限的角色>], company_ids=[<用到的 company_id>])`。
跨公司端点的测试用 admin 角色最省事。

Run(逐文件修):`cd backend && .venv/bin/pytest tests/integration -q`

- [ ] **Step 5: 跑守卫测试 + 全量回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全绿
Run: `cd backend && ruff check .`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add backend/app backend/tests
git commit -m "feat(rbac): 全路由挂权限依赖 + 公司校验 + actor/ip/ua 审计 + 去自报身份"
```

---

### Task 17: 管理端点(`api/routes/admin.py`)

**Files:**
- Create: `backend/app/api/routes/admin.py`
- Modify: `backend/app/schemas/auth.py`(加 admin 相关 schema)
- Modify: `backend/app/main.py`(注册 admin 路由)
- Test: `backend/tests/integration/test_admin.py`

**Interfaces:**
- 全部 `dependencies=[Depends(require(Permission.USER_MANAGE))]`
- Produces:
  - `POST /api/admin/users` `{email, name, password, role_codes: list[str], company_ids: list[str]}` → 创建用户(bcrypt 密码)+ 绑定角色/公司 → 审计 `user.created`
  - `GET /api/admin/users` → 用户列表(不含 password_hash)
  - `PUT /api/admin/users/{id}/roles` `{role_codes}` → 改角色 → 审计 `permission.changed`
  - `PUT /api/admin/users/{id}/companies` `{company_ids}` → 改公司授权 → 审计 `permission.changed`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_admin.py
def test_admin_creates_user(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    from app.models.company import Company
    db.add(Company(id="co-A", name="甲")); db.commit()
    admin = make_user(db, roles=["admin"])
    r = c.post(
        "/api/admin/users",
        headers=auth_headers(admin),
        json={
            "email": "new@x.com", "name": "新人", "password": "pw",
            "role_codes": ["processor"], "company_ids": ["co-A"],
        },
    )
    assert r.status_code == 200
    # 新用户可登录
    login = c.post("/api/auth/login", json={"email": "new@x.com", "password": "pw"})
    assert login.status_code == 200


def test_non_admin_cannot_manage_users(client_with_db, make_user, auth_headers):
    c, db = client_with_db
    user = make_user(db, roles=["processor"], company_ids=["co-A"])
    r = c.get("/api/admin/users", headers=auth_headers(user))
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_admin.py -q`
Expected: FAIL(404)

- [ ] **Step 3: 实现 schema + 路由**

```python
# 追加到 backend/app/schemas/auth.py
class AdminUserCreate(BaseModel):
    email: str
    name: str | None = None
    password: str
    role_codes: list[str] = []
    company_ids: list[str] = []


class AdminUserResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    roles: list[str]
    company_ids: list[str]


class RoleCodes(BaseModel):
    role_codes: list[str]


class CompanyIds(BaseModel):
    company_ids: list[str]
```

```python
# backend/app/api/routes/admin.py
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUserDep, DbSession, require
from app.core.permissions import Permission
from app.core.security import hash_password
from app.models.company import Company
from app.models.user import Role, User
from app.schemas.auth import (
    AdminUserCreate,
    AdminUserResponse,
    CompanyIds,
    RoleCodes,
)
from app.services.audit_service import audit_ctx, record_audit_event

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require(Permission.USER_MANAGE))],
)


def _to_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id, email=user.email, name=user.name,
        roles=[r.code for r in user.roles],
        company_ids=[c.id for c in user.companies],
    )


def _bind_roles(db, user: User, role_codes: list[str]) -> None:
    user.roles = []
    for code in role_codes:
        role = db.query(Role).filter(Role.code == code).first()
        if role is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"未知角色 {code}")
        user.roles.append(role)


def _bind_companies(db, user: User, company_ids: list[str]) -> None:
    user.companies = []
    for cid in company_ids:
        company = db.get(Company, cid)
        if company is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"未知公司 {cid}")
        user.companies.append(company)


@router.post("/users", response_model=AdminUserResponse)
def create_user(
    db: DbSession, actor: CurrentUserDep, request: Request, payload: AdminUserCreate
) -> AdminUserResponse:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱已存在")
    user = User(
        id=str(uuid4()), email=payload.email, name=payload.name,
        password_hash=hash_password(payload.password), status="active",
    )
    db.add(user)
    _bind_roles(db, user, payload.role_codes)
    _bind_companies(db, user, payload.company_ids)
    db.commit()
    db.refresh(user)
    resp = _to_response(user)
    record_audit_event(
        db, company_id=None, actor_id=actor.id, action="user.created",
        entity_type="user", entity_id=user.id, after=resp.model_dump(),
        **audit_ctx(request),
    )
    return resp


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: DbSession) -> list[AdminUserResponse]:
    return [_to_response(u) for u in db.query(User).all()]


@router.put("/users/{user_id}/roles", response_model=AdminUserResponse)
def set_roles(
    db: DbSession, actor: CurrentUserDep, request: Request,
    user_id: str, payload: RoleCodes,
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    before = _to_response(user).model_dump()
    _bind_roles(db, user, payload.role_codes)
    db.commit(); db.refresh(user)
    after = _to_response(user)
    record_audit_event(
        db, company_id=None, actor_id=actor.id, action="permission.changed",
        entity_type="user", entity_id=user.id, before=before, after=after.model_dump(),
        **audit_ctx(request),
    )
    return after


@router.put("/users/{user_id}/companies", response_model=AdminUserResponse)
def set_companies(
    db: DbSession, actor: CurrentUserDep, request: Request,
    user_id: str, payload: CompanyIds,
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    before = _to_response(user).model_dump()
    _bind_companies(db, user, payload.company_ids)
    db.commit(); db.refresh(user)
    after = _to_response(user)
    record_audit_event(
        db, company_id=None, actor_id=actor.id, action="permission.changed",
        entity_type="user", entity_id=user.id, before=before, after=after.model_dump(),
        **audit_ctx(request),
    )
    return after
```

- [ ] **Step 4: 注册路由**

`backend/app/main.py`:`from app.api.routes import admin, audit, auth, files` + `app.include_router(admin.router)`。

- [ ] **Step 5: 跑测试 + 回归 + lint**

Run: `cd backend && .venv/bin/pytest tests/integration/test_admin.py -q && .venv/bin/pytest -q && ruff check .`
Expected: 全绿

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/routes/admin.py backend/app/schemas/auth.py backend/app/main.py backend/tests/integration/test_admin.py
git commit -m "feat(admin): 用户/角色/公司授权管理端点 + 审计"
```

---

## Phase H — 前端完整 RBAC UI

> 前端测试以 `npm run build`(tsc 通过)为主门禁;Playwright 冒烟可选。

### Task 18: 鉴权上下文 + 登录页 + axios 拦截 + 路由守卫

**Files:**
- Create: `frontend/src/api/auth.ts`、`frontend/src/auth/AuthProvider.tsx`、`frontend/src/auth/useAuth.ts`、`frontend/src/auth/RequireAuth.tsx`、`frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/api/client.ts`、`frontend/src/App.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/login`、`GET /api/auth/me`
- Produces:
  - `useAuth() -> { me, token, login(email,pw), logout, hasPermission(p), currentCompanyId, setCurrentCompanyId }`
  - axios 请求注入 `Authorization`;响应 401 → logout + 跳 `/login`

- [ ] **Step 1: api/auth.ts**

```ts
// frontend/src/api/auth.ts
import { client } from "./client";

export interface Me {
  id: string;
  email: string;
  name?: string;
  roles: string[];
  accessible_companies: { id: string; name: string }[] | "all";
}

export async function login(email: string, password: string): Promise<string> {
  const { data } = await client.post("/api/auth/login", { email, password });
  return data.access_token as string;
}

export async function fetchMe(): Promise<Me> {
  const { data } = await client.get("/api/auth/me");
  return data as Me;
}
```

- [ ] **Step 2: axios 拦截器**

`frontend/src/api/client.ts` 加(token 从 localStorage 读;此处定义读写工具):
```ts
const TOKEN_KEY = "fa_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

client.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

client.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      setToken(null);
      if (location.pathname !== "/login") location.assign("/login");
    }
    return Promise.reject(error);
  },
);
```

- [ ] **Step 3: AuthProvider + useAuth**

```tsx
// frontend/src/auth/AuthProvider.tsx
import { createContext, useCallback, useEffect, useState } from "react";
import { fetchMe, login as apiLogin, Me } from "../api/auth";
import { getToken, setToken } from "../api/client";
import { permissionsForRoles } from "./permissions";

interface AuthCtx {
  me: Me | null;
  ready: boolean;
  login: (email: string, pw: string) => Promise<void>;
  logout: () => void;
  hasPermission: (p: string) => boolean;
  currentCompanyId: string | null;
  setCurrentCompanyId: (id: string | null) => void;
}
export const AuthContext = createContext<AuthCtx>(null as never);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const [currentCompanyId, setCurrentCompanyId] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    if (!getToken()) { setReady(true); return; }
    try { setMe(await fetchMe()); } catch { setMe(null); }
    setReady(true);
  }, []);
  useEffect(() => { void loadMe(); }, [loadMe]);

  const login = async (email: string, pw: string) => {
    setToken(await apiLogin(email, pw));
    await loadMe();
  };
  const logout = () => { setToken(null); setMe(null); location.assign("/login"); };
  const hasPermission = (p: string) =>
    permissionsForRoles(me?.roles ?? []).has(p);

  return (
    <AuthContext.Provider value={{ me, ready, login, logout, hasPermission, currentCompanyId, setCurrentCompanyId }}>
      {children}
    </AuthContext.Provider>
  );
}
```
```ts
// frontend/src/auth/useAuth.ts
import { useContext } from "react";
import { AuthContext } from "./AuthProvider";
export const useAuth = () => useContext(AuthContext);
```
```ts
// frontend/src/auth/permissions.ts —— 镜像后端角色→权限映射
const ROLE_PERMS: Record<string, string[]> = {
  admin: ["company_manage","user_manage","template_manage","conversion_process","conversion_confirm","export_run","rule_approve","audit_view","read"],
  template_admin: ["read","template_manage"],
  processor: ["read","conversion_process","conversion_confirm","export_run"],
  reviewer: ["read","conversion_confirm","rule_approve","audit_view"],
  auditor: ["read","audit_view"],
};
export function permissionsForRoles(roles: string[]): Set<string> {
  const s = new Set<string>();
  roles.forEach((r) => (ROLE_PERMS[r] ?? []).forEach((p) => s.add(p)));
  return s;
}
```

- [ ] **Step 4: LoginPage + RequireAuth**

```tsx
// frontend/src/pages/LoginPage.tsx
import { Button, Card, Form, Input, message } from "antd";
import { useAuth } from "../auth/useAuth";

export function LoginPage() {
  const { login } = useAuth();
  const onFinish = async (v: { email: string; password: string }) => {
    try { await login(v.email, v.password); location.assign("/"); }
    catch { message.error("邮箱或密码错误"); }
  };
  return (
    <Card title="登录 FA Tools" style={{ maxWidth: 360, margin: "10vh auto" }}>
      <Form onFinish={onFinish} layout="vertical">
        <Form.Item name="email" label="邮箱" rules={[{ required: true }]}>
          <Input autoFocus />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true }]}>
          <Input.Password />
        </Form.Item>
        <Button type="primary" htmlType="submit" block>登录</Button>
      </Form>
    </Card>
  );
}
```
```tsx
// frontend/src/auth/RequireAuth.tsx
import { Navigate } from "react-router-dom";  // 若项目用 react-router;否则按 App.tsx 现有切页机制改
import { useAuth } from "./useAuth";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { me, ready } = useAuth();
  if (!ready) return null;
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```
> 注:`App.tsx` 现状是 `useState 切页`(非 react-router)。实施者先查 `App.tsx` 实际路由机制:
> 若无 react-router,则在 `App.tsx` 顶层判断 `me` 为空时渲染 `<LoginPage/>`,否则渲染原 AppShell;
> 不引入 react-router 以免扩大改动。RequireAuth 仅在已有 router 时使用。

- [ ] **Step 5: 包裹 App + 构建**

`frontend/src/App.tsx`(或 `main.tsx`)最外层包 `<AuthProvider>`;`me` 为空渲染登录页。
Run: `cd frontend && npm run build`
Expected: exit 0

- [ ] **Step 6: 提交**

```bash
git add frontend/src/auth frontend/src/api/auth.ts frontend/src/api/client.ts frontend/src/pages/LoginPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): 鉴权上下文 + 登录页 + axios 拦截 + 守卫"
```

---

### Task 19: 按权限菜单/按钮 + 公司切换器 + 去自报身份

**Files:**
- Modify: `frontend/src/components/AppShell.tsx`、`frontend/src/tools/registry.ts`
- Modify: 各页面(`UploadPage`、`ConversionRunDetailPage` 等)—— 去掉写死 `user-1`/company,用 `currentCompanyId`;操作按钮按 `hasPermission` 显隐

**Interfaces:**
- Consumes: `useAuth().hasPermission`、`currentCompanyId`、`me.accessible_companies`

- [ ] **Step 1: 工具描述符加 requiredPermission**

`tools/registry.ts` 的 `Tool` 类型加可选 `requiredPermission?: string`;AppShell 渲染菜单时
`registry.filter(t => !t.requiredPermission || hasPermission(t.requiredPermission))`。
审计菜单项标 `audit_view`。

- [ ] **Step 2: 公司切换器**

AppShell 顶部加 Select:
```tsx
const { me, currentCompanyId, setCurrentCompanyId } = useAuth();
const companies = me?.accessible_companies === "all" ? allCompanies : (me?.accessible_companies ?? []);
// "all" 时需另拉公司列表(GET 现有公司端点;若无则展示"全部公司"占位并允许手填/后续补端点)
<Select value={currentCompanyId} onChange={setCurrentCompanyId}
        options={companies.map(c => ({ value: c.id, label: c.name }))} />
```
> 若后端暂无"列出全部公司"端点,跨公司用户(admin/auditor)的切换器先用 me 返回为 "all" 的占位逻辑:
> 允许不选(=全部),list 页不带 company 过滤;写操作页要求显式选公司。记录为后续可加公司列表端点。

- [ ] **Step 3: 去自报身份 + 按钮权限**

各页面凡写死 `user_id: "user-1"` / 固定 company 的地方:删除 `user_id`(后端从 token 取),
company 用 `currentCompanyId`。操作按钮(上传/导出/确认/新建模板等)外层包
`hasPermission("conversion_process")` 等条件渲染/禁用。

- [ ] **Step 4: 构建**

Run: `cd frontend && npm run build`
Expected: exit 0

- [ ] **Step 5: 提交**

```bash
git add frontend/src
git commit -m "feat(frontend): 按权限菜单/按钮 + 公司切换器 + 去自报身份"
```

---

## Phase I — 收尾验收

### Task 20: 全量回归 + lint + 文档

- [ ] **Step 1: 后端全测 + lint**

Run: `cd backend && .venv/bin/pytest -q && ruff check .`
Expected: 全绿

- [ ] **Step 2: 前端构建**

Run: `cd frontend && npm run build`
Expected: exit 0

- [ ] **Step 3: 更新文档**

更新 `docs/handover.md` §11:把"认证/权限""账号加密""审计 ip/UA"从待办移到已完成,
并在 API 端点清单补 `/api/auth/*`、`/api/admin/*`。更新 `docs/gap-analysis.md` P2-1/P2-2/P2-3 状态。

- [ ] **Step 4: 提交**

```bash
git add docs/handover.md docs/gap-analysis.md
git commit -m "docs: W3 安全加固完成,更新交接与差距分析"
```

---

## 自检对照(spec coverage)

- 鉴权 → Task 1(JWT/密码)、9(deps)、10(login/me)✅
- RBAC → Task 3(权限映射)、9(require)、16(全路由挂权限)、17(admin)、19(前端按权限)✅
- 租户隔离 → Task 5(关联表)、9(accessible)、15(列表收窄)、16(写校验)✅
- 字段加密 → Task 2(crypto)、11(列接入)、12(脱敏展示)✅
- SQLite FK pragma → Task 4 ✅
- 审计脱敏 + 补全 → Task 13(redact)、14(ip/ua)、16(actor)、10/17(login/permission 事件)✅
- 前端完整 RBAC UI → Task 18(登录/守卫/拦截)、19(菜单/按钮/公司切换)✅
- 引导管理员 → Task 7 ✅
