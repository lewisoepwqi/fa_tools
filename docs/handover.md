# FA Tools 项目交接文档

> 交接时间：2026-06-27
> 最新提交：`9798958 test: add end-to-end conversion flow smoke test`
> 文档对象：接手后续开发/维护的同学

---

## 1. 一句话现状

银行流水转公司日记账工具的 **MVP 已完整交付并通过端到端验证**：上传银行流水（CSV/XLSX）→ 解析标准化 → 按版本化模板/映射/规则转换 → 预览 + 人工确认 → 导出公司日记账，全链路 SQLAlchemy 持久化 + 审计日志。后端 38 测试全绿、ruff 全绿；前端可构建、Playwright 冒烟通过。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12、FastAPI、SQLAlchemy 2（声明式）、Alembic、Pydantic v2、pydantic-settings、openpyxl |
| 数据库 | 测试 SQLite in-memory；生产 PostgreSQL 16（`docker-compose.yml` + Alembic 迁移已就绪） |
| 前端 | React 18、TypeScript（strict）、Ant Design v5、Vite 5、axios |
| 测试 | 后端 pytest + httpx TestClient；前端 Playwright |
| Lint | ruff（规则 `E,F,I,UP,B`，行长 100） |

> ⚠️ 当前环境**无 Docker**，PostgreSQL 实测留待后续环境。所有测试跑在 SQLite in-memory。

---

## 3. 代码结构

```
fa_tools/
├── AGENTS.md                 # 项目命令与约定（必读）
├── README.md                 # 本地运行 runbook
├── docker-compose.yml        # PostgreSQL 服务
├── docs/
│   ├── handover.md           # 本文件
│   ├── prd-bank-statement-journal.md          # 产品需求
│   ├── technical-design-bank-statement-journal.md  # 技术设计
│   ├── mvp-acceptance-checklist.md            # MVP 验收清单
│   └── superpowers/plans/2026-06-27-bank-statement-journal-mvp.md  # 19 任务实施计划
├── backend/
│   ├── pyproject.toml        # ruff/pytest 配置在此
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py           # FastAPI app + 路由注册
│   │   ├── core/             # config.py, enums.py
│   │   ├── db/               # base.py(Base), session.py(engine/get_db)
│   │   ├── models/           # 22 张 ORM 表（见 §4）
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── api/
│   │   │   ├── deps.py       # DbSession 依赖
│   │   │   └── routes/       # 9 个路由模块（见 §5）
│   │   └── services/         # 纯业务逻辑（见 §6）
│   ├── migrations/versions/0001_initial_schema.py
│   └── tests/
│       ├── conftest.py       # SQLite in-memory + get_db override + create_all
│       ├── fixtures/         # bank_statement_basic.csv / .xlsx
│       ├── unit/             # 纯函数单测
│       └── integration/      # API 集成 + 端到端
└── frontend/
    ├── package.json
    ├── playwright.config.ts
    └── src/
        ├── App.tsx           # 顶层导航（useState 切页）
        ├── api/              # client.ts, files.ts, conversionRuns.ts
        ├── components/       # AppShell, StatusTag, ExceptionTag, VersionBadge
        ├── pages/            # Upload, ConversionRunDetail/List, Bank/JournalTemplate, MappingProfile, Rule, AuditLog
        └── types/conversion.ts
```

代码规模：后端约 **2484 行** Python，**38 个测试**。

---

## 4. 数据模型（22 张表，三层架构）

设计遵循「原始事实层 → 标准流水层 → 公司日记账层」+ 版本化配置 + 全链路审计。

**基础/主体**
- `users`、`roles`、`companies`、`bank_accounts`

**源文件（原始事实层）**
- `source_files`（上传文件元数据 + sha256 + storage_key）

**版本化配置（一经批次引用不可变）**
- `bank_templates` / `bank_template_versions`
- `company_journal_templates` / `company_journal_template_versions`
- `mapping_profiles` / `mapping_profile_versions`
- `rules` / `rule_versions`

**转换批次（核心链路）**
- `conversion_runs`（批次，绑定各版本 ID + summary_json）
- `conversion_run_files`（批次↔源文件）
- `conversion_run_rule_versions`（批次↔规则版本）
- `bank_transactions`（标准流水，含 raw_row_json + 可追溯 source_row_index）
- `journal_preview_rows`（预览行 + output_values_json + status + rule_trace_json）

**人工干预**
- `manual_adjustments`（人工修改：old/new/reason/adjusted_by）
- `confirmations`（确认记录）

**导出与审计**
- `exports`（导出文件元数据）
- `audit_logs`（全链路审计，before/after 快照）

> 关键约定：`IdMixin.id` 是 `String(36)` 主键**无默认值**，插入时必须显式 `str(uuid4())`。所有 `*_json` 列用通用 `JSON` 类型（非 JSONB）→ SQLite 兼容。

---

## 5. API 端点清单（21 个）

> **⚠️ W3 起：除 `/health`、`/api/auth/login` 外，所有端点均要求 `Authorization: Bearer <JWT>` 头；缺失或过期返回 401。写操作额外按角色做 RBAC 检查（见"W3 安全模型"一节），涉及公司数据的操作额外做租户隔离校验。**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查（无需认证） |
| **POST** | **`/api/auth/login`** | **用户登录，返回 JWT access_token（无需认证）** |
| **GET** | **`/api/auth/me`** | **获取当前登录用户信息** |
| **POST** | **`/api/admin/users`** | **创建用户（仅 admin）** |
| **GET** | **`/api/admin/users`** | **列出用户（仅 admin）** |
| **PUT** | **`/api/admin/users/{id}/roles`** | **修改用户角色（仅 admin）** |
| **PUT** | **`/api/admin/users/{id}/companies`** | **修改用户所属公司（仅 admin）** |
| POST | `/api/files/upload` | 上传流水文件（multipart）→ 持久化 source_file |
| POST | `/api/bank-templates` / GET | 银行模板 create/list（版本化） |
| POST | `/api/journal-templates` / GET | 日记账模板 create/list |
| POST | `/api/mapping-profiles` / GET | 映射方案 create/list |
| POST | `/api/rules` / GET | 规则 create/list |
| POST | `/api/conversion-runs` | 发起转换 → 解析+规则+映射+预览，全链路持久化 |
| PATCH | `/api/preview-rows/{row_id}` | 人工修改字段 |
| POST | `/api/preview-rows/{row_id}/confirm` | 确认预览行 |
| POST | `/api/conversion-runs/{run_id}/exports` | 导出 CSV/XLSX |
| GET | `/api/exports/{export_id}/download` | 下载导出文件 |
| GET | `/api/audit-logs` | 审计日志列表（仅 admin/auditor） |

**审计事件（12 类）**：`file.uploaded`、`bank_template.created`、`journal_template.created`、`mapping_profile.created`、`rule.created`、`conversion_run.created`、`preview_row.adjusted`、`preview_row.confirmed`、`export.created`；W3 新增：`login`（成功/失败均记录）、`user.created`、`permission.changed`。

---

## 6. 服务层（纯函数，便于单测）

| 文件 | 职责 |
|---|---|
| `parser_service.py` | CSV/XLSX 解析、表头检测、金额/日期标准化 → `StandardBankTransaction` |
| `mapping_service.py` | `apply_mappings`：field/fixed/rule_output/concat/manual |
| `rule_service.py` | `apply_rules`：条件匹配、冲突检测、规则轨迹 |
| `conversion_service.py` | `build_preview_row`（单行）+ `run_conversion`（整批编排 + 持久化） |
| `confirmation_service.py` | 人工修改 + 确认（DB 持久化） |
| `export_service.py` | CSV/XLSX 导出 |
| `audit_service.py` | `build_audit_event`（纯）+ `record_audit_event`（持久化） |
| `template_service.py` | 银行/日记账模板 CRUD（DB 持久化） |
| `file_service.py` | 文件落盘 + sha256 |

> 规则引擎与映射引擎是**纯函数**（无 DB），便于单测；持久化在路由/编排层接入。

---

## 7. 运行指南

```bash
# 后端测试（必须用 .venv，PEP 668 阻止系统 python）
cd backend && .venv/bin/pytest -q

# 后端 lint（ruff 在 ~/.local/bin，不在 .venv）
cd backend && ruff check .

# 启动后端开发服务器
cd backend && .venv/bin/uvicorn app.main:app --reload

# 前端构建 / 开发 / e2e
cd frontend && npm run build
cd frontend && npm run dev          # http://localhost:5173
cd frontend && npm run e2e          # 首次需 npx playwright install chromium

# 生产数据库（需 Docker）
docker compose up -d postgres
cd backend && alembic upgrade head
```

> 完整约定见 `AGENTS.md`。
>
> 数据运维（PG 实测/JSON-JSONB/异步 rollout）见 `docs/data-ops-runbook.md`。

---

## 8. 测试状态

- **后端：38 个测试全绿**（1 个非阻塞 Starlette httpx deprecation warning）
  - 单元：parser（7）、mapping（8）、rule（2）、conversion（1）、template/migration 契约（4）、audit（1）、export（2）
  - 集成：上传、模板创建、转换批次、确认、审计、导出、下载
  - **端到端**：`test_full_conversion_flow_end_to_end` 覆盖 上传→转换→修改→确认→导出→下载→审计 全链路
- **前端**：`npm run build` exit 0；Playwright `1 passed`
- **Ruff**：全绿（Task 1–6 遗留的 62 个历史违规已于本次清理归零）

---

## 9. 本次会话完成的工作（21 个提交，Task 7 → 收尾）

接手时项目处于 Task 6 完成（仅文件上传 + 解析 + 映射引擎，全内存）。本次会话按 subagent-driven 工作流（每任务 TDD + 实现→规格审查→质量审查→提交）完成：

| 阶段 | 提交范围 | 内容 |
|---|---|---|
| Task 7–13 后端服务 | `eee3e7c`→`512903d` | 规则引擎、转换预览、CRUD API、转换批次、确认、导出、审计边界 |
| Task 14–17 前端 | `d3627c8`→`6ea44a1` | 脚手架、上传/预览/管理页面、Playwright |
| Task 18 持久化（5 阶段） | `6127ad5`→`bb1aa35` | DB 基础设施→配置→转换→确认→审计，内存全迁 SQLAlchemy |
| 收尾 | `931fd8a`→`9798958` | docs 提交、AGENTS.md、ruff 清零、端到端冒烟 |

完整提交历史：`git log --oneline`（共 27 个提交，含 Task 1–6 的 6 个）。

---

## 10. 关键架构与设计决策

1. **版本化不可变**：模板/映射/规则一经批次引用不可改；编辑创建新 `*_versions` 行（`version_no` 递增）。批次快照绑定当次版本 ID，保证历史可追溯。
2. **保守确认**：未命中规则、必填缺失、规则冲突一律进入 `needs_confirmation`，绝不静默自动入账。自动确认需显式 `allow_auto_confirm`。
3. **三层模型**：原始事实（source_files/raw_row_json）→ 标准流水（bank_transactions）→ 公司日记账（journal_preview_rows）。任意导出行可回溯到原始文件 + 行号。
4. **路径解析走 DB 元数据**：转换时按 `source_file_id` 查 `source_files.storage_key` 拼路径，**不信任请求入参** → 天然防路径穿越（不存在的 id → 404）。
5. **纯函数 + 持久化分层**：规则/映射引擎是纯函数（无 DB，易测）；持久化在路由/编排层。`run_conversion` 是整批编排的唯一入口。
6. **测试 DB 策略**：conftest 用 SQLite in-memory + `StaticPool`（共享连接）+ override `get_db` + `create_all`。模型用通用 `JSON` 类型保证 SQLite 兼容。

---

## 11. 已知后续项 / 技术债务

> **完整的 PRD 合规缺口（含本节之外的"真缺口"）见 [`gap-analysis.md`](./gap-analysis.md)**。
> 该文档按 P0/P1/P2 分级、附 PRD 依据与代码证据，并区分"验收清单标 [x] 但实际未满足"与"主动推迟的非 MVP 项"。

记录在 `docs/mvp-acceptance-checklist.md`：

- **PostgreSQL 实测**：当前无 Docker，测试全在 SQLite。生产前需 `docker compose up -d postgres && alembic upgrade head` 验证迁移在 PG 上无误（注意：模型用通用 `JSON`，PG 会建为 `JSON` 而非 `JSONB`；如需 JSONB 索引/查询性能需后续调整）。
- ✅ **W3 已完成 — 账号字段加密**：`bank_accounts.account_no_encrypted`、`bank_transactions.counterparty_account_no_encrypted` 已由 W3 引入 SQLAlchemy `EncryptedString` 类型（Fernet 对称加密），API 响应自动做展示掩码（前四后四、中间 `****`）。
- **去重与余额连续性**：`bank_transactions.row_hash` 当前留空。需实现去重哈希（银行流水号优先，缺失用组合哈希）+ `DUPLICATE_IN_BATCH`/`DUPLICATE_HISTORY`/`BALANCE_DISCONTINUITY` 异常检测。
- **规则引擎健壮性**：`rule_service` 的 `gte`/`lte` 操作符在字段为 `None` 时会抛 `InvalidOperation`（`balance` 等可选字段）。当前计划内规则只用 `contains`/`eq` 不触发；接入数值规则前需加 None 防护（TDD 补一个用例）。
- **前端分包**：AntD 整包打入单 chunk（~1MB）。需 `manualChunks` 或动态 import 拆分。
- **AntD message context**：使用了静态 `message` API，v5 会一次性警告；建议接入 `App` 组件的 `message` context。
- ✅ **W3 已完成 — 审计 ip/UA**：`ip_address`/`user_agent` 已由 W3 从 FastAPI `Request` 对象提取并持久化到 `audit_logs`。
- ✅ **W3 已完成 — 审计脱敏**：审计快照（`before_state`/`after_state`）中的敏感字段（账号等）在写入 `audit_logs` 前由 `audit_service` 统一做 `redact` 处理，不落明文。
- **金额模式**：`parser_service` 仅实现 `INCOME_EXPENSE_COLUMNS` 一种；enums 定义了 4 种（`SINGLE_AMOUNT_WITH_DIRECTION`/`DEBIT_CREDIT_COLUMNS`/`SIGNED_AMOUNT`），其余待补。
- ✅ **W3 已完成 — 认证/权限**：已实现 JWT Bearer 认证（HS256，8 小时有效期）+ 5 角色 RBAC（admin/template_admin/processor/reviewer/auditor）+ per-company 租户隔离。见下方"W3 安全模型"节及 `app/core/permissions.py`。
- **异步任务**：解析/规则匹配当前同步。大文件（>10000 行）需引入 Celery/RQ（技术设计已规划）。

---

### W3 安全模型（2026-06-29 实施）

| 维度 | 实现 |
|---|---|
| 鉴权 | JWT Bearer，HS256，有效期 `settings.access_token_ttl_minutes`（默认 480 min）；`POST /api/auth/login` 签发，其余端点 `get_current_user` 依赖强制校验 |
| RBAC | 权限粒度；5 角色见 `app/core/permissions.py`：`admin`（全权）/ `template_admin`（模板配置）/ `processor`（上传+转换+导出）/ `reviewer`（审核确认）/ `auditor`（只读审计）；`require_permission(perm)` 装饰器在路由层检查 |
| 租户隔离 | `user_companies` 多对多；`admin`/`auditor` 跨公司可见；其余角色：list 端点收窄到本用户公司，写操作走 `require_company_access` 校验 |
| 字段加密 | Fernet `EncryptedString` 自定义 SQLAlchemy 类型；受保护列：`bank_accounts.account_no_encrypted`、`bank_transactions.counterparty_account_no_encrypted`；API 响应展示掩码（`****`），审计快照 redact |
| 引导管理员 | 迁移 `0005_seed_bootstrap_admin.py` 按 `settings.bootstrap_admin_email` / `settings.bootstrap_admin_password` 播种初始 admin；**生产必须修改默认值**（见下方部署须知） |

---

### 生产部署须知（W3）

> 以下配置当前使用**不安全的开发默认值**，上生产前**必须**通过环境变量覆盖：

1. **`SECRET_KEY`**（JWT HMAC 密钥）：当前默认 `"development-secret"`，不足 32 字节会触发 `InsecureKeyLengthWarning`。生产须设置 ≥32 字节强随机密钥，例如：
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. **`FIELD_ENCRYPTION_KEY`**（Fernet 字段加密密钥）：当前为固定开发 Fernet key。生产须独立生成并通过环境变量注入：
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   ⚠️ 更换 key 后既有密文**无法解密**，须先迁移数据或重新加密。

3. **`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`**：默认 `admin@example.com` / `changeme`。首次部署迁移后必须立即通过管理员接口改密，或在迁移前用环境变量设置强密码。

4. **已知功能缺口 → 已划入 W5**（见下方「W3 收尾结论」）：
   - 跨公司角色（admin/auditor）前端无法指定具体公司创建数据——缺 `GET /api/companies` 列表端点，前端公司选择器写死。
   - 模板/规则等的启用/停用 Switch 前端未做权限门控（processor/reviewer 也能看到开关，但点击会被后端拒绝，属技术债）。

---

### W4 收尾结论（2026-06-30 闭合，分支 `feat/w4-data-ops`）

W4 数据运维完成，**后端 325 测试全绿 + ruff clean + 前端 build exit 0**。7 任务 TDD + 逐任务复审 + opus 整分支最终复审 + 必修 I1 闭合。详细操作见 `docs/data-ops-runbook.md`。

**现状修正**：开工探查修正两处过时认知——① **P0-2 批次快照版本 FK 已实现**（`run_conversion`/`run_conversion_from_config` 已赋值 3 个版本 FK 列，消费端已用，W4 不含 P0-2）；② 迁移契约有半成品但缺 `compare_metadata` 自动比对。

**W4 交付**：
- **A 迁移契约**：`compare_metadata` autogenerate 无 diff 测试（钉死 conftest `create_all` 与迁移两条 schema 路径；**首跑即抓到真 bug**——迁移 0003 建了 `builtin_field_overrides.created_at` 但 ORM 模型漏声明，已补）。
- **B PG 实测基础设施**：`conftest` 按 `test_database_url` 切库（SQLite 默认 / PG 可选，`requires_pg` skip）；`docker-compose` postgres 加 healthcheck；**GitHub Actions CI**（`backend-sqlite` 全量+ruff / `backend-pg` postgres service + `alembic upgrade head` + 全量）；JSON 保持通用 `JSON`（**不迁 JSONB，YAGNI**——当前无 DB 层 JSON 查询）+ `data-ops-runbook.md`。
- **C 大文件鲁棒性**：`RunStatus` 状态机（pending/processing/completed/failed）+ `run_conversion` 拆为 `create_pending_run`/`process_conversion_run`（**失败 rollback→重取→FAILED+error_message，不再整请求 500**）+ 迁移 0006（`error_message` 列）+ **流式解析**（XLSX 真流式 `iter_rows`；CSV 受限于编码探测仍 O(file)，仅行迭代惰性）+ failed 批次错误暴露（列表/详情 + 前端 `Alert`）。`run_conversion` 对外契约不变。

**显式推迟（spec §1 Out + §5，均已文档化）**：Celery/RQ 真异步 worker + 202 + 前端轮询（无 Docker/broker；状态机+流式已把接入收敛为「`process_conversion_run` 改投递 Celery」的小改动，设计见 spec §5 / runbook §4）；JSONB 迁移（无查询需求，路径已文档化）；去重哈希/余额连续性（P1-3，引擎层非数据运维）。

**已知 follow-up（Minor，opus 复审记录，非阻塞）**：同步路径 4xx（源文件 404）遗留 PENDING 孤儿批次；`compare_metadata` 仅 SQLite 实测、PG 侧仅 `alembic upgrade` smoke；`FAILED` 分支重取 run 无 None 守卫（不触发）；`PROCESSING` 未独立提交（异步化时补）；`BuiltinFieldOverride` 未复用 `TimestampMixin`；CSV「内存有界」措辞偏强。

**CI 首次运行**：`.github/workflows/ci.yml` 在本 PR 推送后首次在 GitHub 运行；需观察 `backend-pg` job 是否暴露其他 SQLite-only 假设（类型/排序/server_default 在 PG 的差异）。

**W4 工作流自此闭合，三个工作流（W3→W5→W4）全部收口。**

---

### W5 收尾结论（2026-06-30 闭合，分支 `feat/w5-frontend`）

W5 前端收口与分页完成，**后端 318 测试全绿 + ruff clean + 前端 `npm run build` exit 0**。经 12 任务 TDD + 逐任务复审 + opus 整分支最终复审 + 必修闭合。

**重大现状修正**：开工探查发现 gap-analysis（2026-06-27）已严重过时——4 实体（银行模板/日记账模板/映射方案/规则）的**编辑=新版本（`POST /{id}/versions`）、版本历史、启停（`PATCH /{id}/status`）、规则 reorder、银行模板 detect 端点，及对应前端新建/编辑/版本历史/停用/删除 UI，连同 `*.modified`/`*.disabled`/`rule.priority_changed` 审计，均已在 W3 期落地**。W5 因此不重建编辑能力，收敛为 7 项真实剩余缺口。

**W5 交付**：
- 后端：批次 `summary` 增分状态计数（auto/needs/conflict）；`preview-rows` 端点加 `status` 过滤；4 实体 list + 批次 list 接 `Page[T]` 分页；新增平台共享 `GET /api/companies`（按可访问集收窄）；规则 reorder 审计按被改规则记 `company_id`（修跨公司丢归属）；规则列表改按最新版本 `priority` 升序。
- 前端：`Page<T>` + 5 列表页服务端分页（切换公司重置页码）；批次详情改用 `preview-rows` 分页端点 + 统计取 `summary`（内联/独立两形态分支）；日记账按模板 `columns_json` 动态渲染列与编辑字段；规则列表 `@dnd-kit` 拖拽重排（offset 基准 priority）；公司选择器修复（admin/`'all'` 可选具体公司）；停用/删除按钮 + registry 菜单补权限门控。
- handover §4 两项（`GET /api/companies` 公司选择器、启停 Switch 权限门控）**已在 W5 闭合**。

**已知 follow-up（Minor，非阻塞，opus 复审记录）**：
- **e2e 全缺**：纯前端交互（拖拽/公司选择/详情分页/动态列）仅 `npm run build` 门禁；本环境 WSL2 跑 e2e 超时（`tests/conversion-flow.spec.ts` 存在但需后端/启动慢）。建议有 CI/可跑 e2e 环境时优先补：① 规则拖拽→reorder→reload 顺序持久化；② admin 选具体公司后可创建。
- 批次详情 `getConversionRun` 仍全量返回 `preview_rows`（分页只省了表格渲染、未省网络）；可后续提供剥离预览行的轻量 detail。
- 动态列丢失「金额」右对齐（需后端 `columns_json` 携带列类型信息才能通用解决）；`templates` 菜单按 `template_manage` 门控会挡住只读角色从导航进入查看（spec §3.6 本意，如产品需要可降为 `read`）。
- 预览行加载失败静默（无 `message.error`、`rowsTotal` 未归零）；`listCompanies` useEffect 缺 `AbortController` cleanup；规则 reorder 对 priority 未变规则仍写审计（预存行为）；`_extract_column_names` dict 分支无生产者（防御代码，键名约定臆测）。

**跨工作流依赖**：**P0-2（批次快照已保存版本 ID）** 的版本机制已具备，但其实现落在转换管道（`conversion_service`），**归 W4**；preview-rows 异常码的跨页服务端过滤依赖 W4 的 JSON 查询可移植性方案。

**W5 工作流自此闭合**，待提 PR 合并。

---

### W3 收尾结论（2026-06-29 闭合）

W3 安全加固已随 **PR #13 合并到 main**，本次收尾盘点结论：

- **验证全绿**：后端 `.venv/bin/pytest -q` → **303 passed**；lint → `.venv/bin/python -m ruff check .` → All checks passed（注：本环境 ruff 装在 `.venv` 里，用 `python -m ruff` 调用，PATH 上无独立 `ruff`）；前端 `npm run build` → exit 0（仅既有 AntD 单 chunk ~1.3MB 体积警告，属已记录技术债，非阻塞）。
- **spec 残留核对**：W3 spec §6.2 注脚明确——`*.modified` / `*.disabled` / `rule.priority_changed` 审计事件依赖各自编辑端点，**W3 不强制补全**。这些编辑端点（gap P0-1 / P2-4）现已划归 **W5**，对应审计事件随 W5 一并补齐。W3 自身范围（鉴权 / RBAC / 租户隔离 / 字段加密 / SQLite FK pragma / 审计脱敏 + login/user.created/permission.changed）已全部落地。
- **§4 两项功能缺口 → 推迟并入 W5**（决策依据：两项均为前端能力且依赖 W5 端点）：
  1. `GET /api/companies` 列表端点 + 前端公司选择器去写死——与 W5「上传页配置选择器去写死」（gap §5 #3）同源，公司切换器需该 list 端点。归 W5。
  2. 模板/规则启停 Switch 前端权限门控——依赖 W5 的 `PATCH /{id}/status` 端点 + 前端 RBAC 门控。归 W5。
- **顺带发现（待 W5 brainstorm 校准）**：代码库已超出 `gap-analysis.md`（2026-06-27 生成）的描述，新增了「自定义字段」相关能力（`CustomFieldPage`、`BankTemplateWizard`、`useStandardFields`、custom-fields 端点等）。W5 开工前需重新核对 gap §5 前端缺口清单，避免按过时清单返工。

**W3 工作流自此闭合**，剩余项去向如上，全部转入 W5 / W4。

---

## 12. 给接手人的建议

1. **先跑一遍验证**：`cd backend && .venv/bin/pytest -q`（38 passed）+ `cd frontend && npm run build && npm run e2e`，确认本地环境 OK。
2. **读三份文档建立全局观**：`docs/prd-*.md`（要什么）→ `docs/technical-design-*.md`（怎么设计）→ `docs/mvp-acceptance-checklist.md`（验收到哪）。
3. **改后端先看 `AGENTS.md`**：命令、约定、已知项都在里面，避免重复摸索（如 ruff 不在 venv、PEP 668、SQLite 测试策略）。
4. **延续工作流**：本项目用 subagent-driven + TDD + conventional commits + 每任务审查。继续开发建议沿用：先写测试看失败 → 实现 → ruff+pytest 验证 → 单任务提交。
5. **下一步优先级建议**（按价值）：① PostgreSQL 实测 + 修 JSON→JSONB → ② 账号加密 → ③ 去重/余额连续性 → ④ 认证/RBAC → ⑤ 异步任务。前端分包/规则健壮性等可穿插。
6. **持久化改动注意**：服务函数签名已带 `db: Session`；新增 create 端点记得调 `record_audit_event`；新增可选字段记得 `IdMixin` 要显式 id；list 端点用 N+1 查 latest version（MVP 可接受，量大时优化）。

---

## 13. 环境/工具备忘

- Python：仅 `python3`（系统），`backend/.venv` 是虚拟环境；**不要** `pip install` 到系统（PEP 668）。
- ruff：`/home/lewis/.local/bin/ruff`（on PATH），**不在** `.venv/bin/`。
- Node：v22.20.0，npm 10.9.3。
- 文件落盘：上传 → `.local/uploads/`，导出 → `.local/exports/`（相对 backend cwd；gitignored）。
- 无 Docker：`docker` 命令不存在，PostgreSQL 实测待有 Docker 的环境。
