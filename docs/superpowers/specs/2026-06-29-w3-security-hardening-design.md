# 设计:安全加固(W3)

> 日期:2026-06-29 · 状态:已通过头脑风暴评审,待用户复核
> 范围:**W3** —— 鉴权 / RBAC / 租户隔离 / 字段加密 / SQLite FK pragma / 审计脱敏。
> 前置:W0+W1(转换核心)、W2(API 健壮性)已合并。
> 依据:`docs/gap-analysis.md` §4(P2-1 无认证、P2-2 RBAC、P2-3 审计补全)、
> `docs/handover.md` §11(账号加密、审计 ip/UA、认证/权限)、PRD §6.10 / §7。

## 0. 定位

W2 收口后端 API 契约;W3 给平台补上**安全底座**:登录鉴权、五角色 RBAC、按公司的租户隔离、
敏感账号字段加密 + 展示脱敏、SQLite 外键约束生效、审计日志脱敏与补全。
改动以**平台共享层**为主(`app/core`、`app/api`、`app/services`、`app/models`),工具层
(`tools/bank_journal`)只需在路由挂权限依赖、把自报身份(payload 里的 `user_id`)换成登录态。

**交付物**:后端全做 + 前端完整 RBAC UI(登录页、鉴权上下文、axios 拦截、按权限隐藏菜单/按钮、公司切换器)。

### YAGNI 取舍(已确认)
- 不做 refresh token(access token 过期重新登录)。
- 不做可搜索/确定性加密(账号仅加密存储,不支持按账号查重/匹配)。
- 不做账号明文解密权限/端点(明文永不出 API)。
- 不做密码重置/找回流程(管理员重置即可)。

---

## 1. 认证(鉴权)

### 1.1 密码与令牌
- `app/core/security.py`:
  - 密码哈希用 **bcrypt**(`bcrypt` 包直连,不引 passlib)。`hash_password` / `verify_password`。
  - JWT 用 **PyJWT**,HS256,密钥取 `settings.secret_key`。
  - claims:`{sub: user_id, roles: [code...], exp}`。有效期默认 8h,可配 `settings.access_token_ttl_minutes`(默认 480)。
  - `create_access_token(user)` / `decode_access_token(token) -> claims`(过期/非法 → 抛,由依赖转 401)。

### 1.2 端点(平台共享层,无工具前缀)
- `POST /api/auth/login`:入参 `{email, password}` → 校验 → 返回 `{access_token, token_type: "bearer"}`。
  - 失败(用户不存在/密码错/账号停用)统一返回 401(不区分以防枚举)。
  - 写审计 `login`(成功);失败也写一条 `login`(标记失败,actor 取尝试的 user_id 或 null)。
- `GET /api/auth/me`:返回当前用户 `{id, email, name, roles: [code...], accessible_companies: [{id, name}] | "all"}`。
  前端据此渲染菜单/按钮/公司切换器。

### 1.3 引导首个管理员
- Alembic **数据迁移**播种:5 个角色(见 §2)+ 一个初始管理员(邮箱/密码取
  `settings.bootstrap_admin_email` / `settings.bootstrap_admin_password`,缺省给开发用默认值并在非
  development 环境校验必须显式设置),并把其加入 `user_roles`(admin)。
- 初始管理员的 `accessible_companies` = 全公司(管理员角色天然跨公司,见 §3)。

---

## 2. RBAC(权限模型)

**权限粒度优先**(不在路由里直接判角色),便于审计与未来扩展。

### 2.1 角色(对齐 PRD §7,code 固定)
| code | 名称 | 职责 |
|---|---|---|
| `admin` | 管理员 | 公司/账套/用户/角色/基础配置 |
| `template_admin` | 模板管理员 | 银行模板/公司模板/映射/规则 |
| `processor` | 财务处理员 | 上传/处理/预览/人工确认/下载 |
| `reviewer` | 财务复核员 | 复核批次/查看确认/批准规则启用 |
| `auditor` | 审计查看员 | 只读历史与日志 |

### 2.2 权限枚举(`app/core/permissions.py`)
`Permission`(str enum)初版:
- `COMPANY_MANAGE`、`USER_MANAGE`(用户/角色/公司授权)
- `TEMPLATE_MANAGE`(模板/映射/规则的增改停用/新版本)
- `CONVERSION_PROCESS`(上传/发起转换/人工修改)
- `CONVERSION_CONFIRM`(确认预览行)
- `EXPORT_RUN`(导出/下载)
- `RULE_APPROVE`(批准规则启用)
- `AUDIT_VIEW`(查看审计日志)
- `READ`(列表/详情只读 —— 所有角色都有)

### 2.3 角色→权限映射
```
admin          → 全部
template_admin → READ, TEMPLATE_MANAGE
processor      → READ, CONVERSION_PROCESS, CONVERSION_CONFIRM, EXPORT_RUN
reviewer       → READ, CONVERSION_CONFIRM, RULE_APPROVE, AUDIT_VIEW
auditor        → READ, AUDIT_VIEW
```
> 注:`processor` 兼具 PROCESS + CONFIRM(MVP 单人闭环);`reviewer` 复核可确认。后续若需严格
> 双人复核(处理与确认分离),收紧 `processor` 的 CONFIRM 即可,不动结构。

### 2.4 依赖
- `app/api/deps.py` 新增:
  - `CurrentUser`(Annotated dep):从 `Authorization: Bearer` 解析 → 查 user(校验 status=active)→
    装配 `roles`、`permissions`(并集)、`accessible_company_ids`(或全公司标记)。401 当令牌缺失/非法/用户停用。
  - `require(*perms: Permission)`:返回一个依赖,缺任一权限 → 403。
  - `require_company_access(company_id)`:校验 company_id 在当前用户授权集(管理员/审计员跳过)→ 否则 403。

---

## 3. 租户隔离

### 3.1 数据模型
- 新增关联表(平台共享层 models):
  - `user_roles`(user_id, role_id) —— 多对多。
  - `user_companies`(user_id, company_id) —— 多对多,定义用户可访问的公司集。
- `admin`、`auditor` 角色视为**跨公司**:`accessible_company_ids` 解析为「全公司」,不受 `user_companies` 约束。
  其余角色仅能访问 `user_companies` 中授权的公司。

### 3.2 强制点
- **写/读单实体**:凡请求带 `company_id`(payload 或路径派生)→ `require_company_access` 校验。
- **列表端点**:按 `accessible_company_ids` 收窄查询(跨公司用户不收窄)。涉及
  conversion-runs / templates / mappings / rules / custom-fields / audit-logs / files 等已带 `company_id` 的实体。
- **派生实体**(preview_rows / exports 等无直接 company_id):经其所属 conversion_run 的 company_id 间接校验。
- **actor 身份**:路由**不再信任** payload 里的 `user_id` —— 一律取自 `CurrentUser`。
  `company_id` 仍由请求携带但必须通过校验(不静默改写)。

### 3.3 管理端点(`app/api/routes/admin.py`,需 `USER_MANAGE`)
- 用户 CRUD(创建用户=设邮箱+初始密码 bcrypt 入库)、分配角色(`user_roles`)、授权公司(`user_companies`)。
- 这些变更写审计:`user.created` / `permission.changed`(角色/公司授权变更)。

---

## 4. 字段加密 + 展示脱敏

### 4.1 加密机制
- `app/core/crypto.py`:Fernet(`cryptography` 库)对称加密,随机 IV(Fernet 自带)。
  密钥取 `settings.field_encryption_key`(base64 url-safe 32B Fernet key);非 development 环境缺失则启动报错,
  development 给固定开发 key。
- SQLAlchemy `TypeDecorator` **`EncryptedString`**:`process_bind_param` 加密、`process_result_value` 解密,
  模型层透明。落到现有两列:
  - `bank_accounts.account_no_encrypted`
  - `bank_transactions.counterparty_account_no_encrypted`
- **迁移注意**:列类型变更不需改 schema(底层仍 String);存量明文数据本环境为空(SQLite/无生产数据),
  不做回填迁移;若未来有 PG 存量,另写一次性回填脚本(本 spec 不含)。

### 4.2 展示脱敏
- 响应 schema 层对账号只返回掩码 `mask_account(s) -> "****" + s[-4:]`(不足 4 位全掩)。
- 完整明文**不出任何 API**。涉及 bank_account 详情/列表响应、conversion 预览/导出响应中的对手账号字段。
- 导出文件(CSV/XLSX):账号列同样输出掩码(避免明文落地到导出文件)。

---

## 5. SQLite 外键 pragma

- `app/db/session.py`:`@event.listens_for(engine, "connect")` 对 SQLite 连接执行
  `PRAGMA foreign_keys=ON`(非 SQLite 不执行,PG 无影响)。
- 同步在 `tests/conftest.py` 的测试 engine 上挂同样监听(测试库才能真正校验 FK,
  暴露此前被静默忽略的悬挂外键)。
- 风险:开启后既有测试若存在「插入悬挂 FK」会暴露失败 —— 视为**真问题**逐个修(TDD 期间处理)。

---

## 6. 审计脱敏 + 补全

### 6.1 脱敏
- `app/services/audit_service.py` 写 `before_json` / `after_json` 前过滤敏感键:
  `password_hash`、`account_no` / `*_account_no*`、`access_token` / `token`、`field_encryption_key` 等
  → 账号类掩码、密钥/口令类剔除或置 `"***"`。集中在一个 `redact(payload: dict) -> dict` 纯函数(可单测)。

### 6.2 补全
- `actor_id` 取自 `CurrentUser`(不再 `user-1`)。
- `ip_address` / `user_agent` 从 `Request` 提取(`record_audit_event` 增 `request` 入参或在路由层传入)。
- 新增审计事件:`login`(成功/失败)、`user.created`、`permission.changed`。
  其余 `*.modified` / `*.disabled` 等依赖各自端点(属 W4 模板管理编辑能力),本 spec 不强制补全。

---

## 7. 前端(完整 RBAC UI)

- **鉴权上下文** `AuthProvider`:持 `token`(localStorage)+ `me`(用户/角色/权限/可访问公司)。
- **登录页** `/login`:邮箱+密码 → `POST /api/auth/login` → 存 token → 拉 `/me` → 跳首页。
- **axios 拦截器**(`api/client.ts`):请求注入 `Authorization`;响应 401 → 清 token + 跳登录。
- **路由守卫**:未登录访问受保护页 → 重定向 `/login`。
- **菜单/按钮按权限隐藏**:`tools/registry.ts` 工具描述符 + AppShell 菜单按 `permissions` 过滤;
  页面内操作按钮(导出/确认/编辑等)按权限禁用/隐藏。
- **公司切换器**:跨公司用户(admin/auditor)可选「全部/某公司」;单/多公司用户按授权集。
  选中公司作为 list 端点过滤 + 上传/转换默认 company_id(替换现状写死的 user-1/company)。
- **去除自报身份**:前端不再在 payload 里塞 `user_id`(actor 由后端 token 决定)。

---

## 8. 模块边界与可测性

| 单元 | 职责 | 依赖 | 测试 |
|---|---|---|---|
| `core/security.py` | 密码哈希、JWT 签发/校验 | bcrypt、PyJWT、settings | 纯函数单测(哈希往返、token 往返、过期) |
| `core/crypto.py` | Fernet 加解密、账号掩码 | cryptography、settings | 纯函数单测(加解密往返、掩码) |
| `core/permissions.py` | 权限枚举、角色→权限映射 | 无 | 单测(映射完整性) |
| `api/deps.py` | CurrentUser / require / require_company_access | security、permissions、DB | 集成测(401/403/放行) |
| `api/routes/auth.py` | 登录、me | deps、security、audit | 集成测 |
| `api/routes/admin.py` | 用户/角色/公司授权 | deps、audit | 集成测 |
| `services/audit_service.py` | redact + 补全 actor/ip/UA | Request | 纯函数单测(redact)+ 集成 |
| `db/session.py` | SQLite FK pragma | event | 集成测(FK 约束生效) |

---

## 9. 执行顺序(建议,TDD)

1. `core/security` + `core/crypto` + `core/permissions`(纯函数,先测)。
2. SQLite FK pragma(独立、低风险,先开,修暴露的 FK 测试)。
3. 模型:`user_roles`、`user_companies` + 关系 + 迁移 + 角色/管理员播种。
4. `deps`(CurrentUser / require / require_company_access)+ `auth` 路由。
5. 字段加密 TypeDecorator 接入两列 + 展示脱敏 schema。
6. 审计脱敏 + 补全(actor/ip/UA + login/permission 事件)。
7. 给所有工具路由挂权限依赖 + 去自报身份 + 列表租户过滤(逐路由,集成测护航)。
8. `admin` 路由(用户/角色/公司授权管理)。
9. 前端:鉴权上下文 + 登录页 + 拦截器 + 守卫 + 菜单/按钮过滤 + 公司切换器。

---

## 10. 验收

- 后端:`.venv/bin/pytest -q` 全绿(含新增鉴权/RBAC/隔离/加密/FK/脱敏用例);`ruff check .` 全绿。
- 未带 token 访问受保护端点 → 401;越权角色 → 403;越权公司 → 403。
- DB 中账号列为密文;API 响应/导出文件中账号为掩码;审计 json 无明文敏感字段。
- SQLite 下悬挂外键被拒。
- 前端:登录闭环可用,过期/无权自动跳登录,菜单/按钮按角色显隐,公司切换生效;`npm run build` 通过。
