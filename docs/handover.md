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

## 5. API 端点清单（15 个）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
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
| GET | `/api/audit-logs` | 审计日志列表 |

**审计事件（9 类，在 create 端点自动记录）**：`file.uploaded`、`bank_template.created`、`journal_template.created`、`mapping_profile.created`、`rule.created`、`conversion_run.created`、`preview_row.adjusted`、`preview_row.confirmed`、`export.created`。

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

记录在 `docs/mvp-acceptance-checklist.md`，均为**非 MVP**：

- **PostgreSQL 实测**：当前无 Docker，测试全在 SQLite。生产前需 `docker compose up -d postgres && alembic upgrade head` 验证迁移在 PG 上无误（注意：模型用通用 `JSON`，PG 会建为 `JSON` 而非 `JSONB`；如需 JSONB 索引/查询性能需后续调整）。
- **账号字段加密**：`bank_accounts.account_no_encrypted`、`bank_transactions.counterparty_account_no_encrypted` 当前存**明文**（命名预留）。需引入加密（如 Fernet）+ 展示脱敏。
- **去重与余额连续性**：`bank_transactions.row_hash` 当前留空。需实现去重哈希（银行流水号优先，缺失用组合哈希）+ `DUPLICATE_IN_BATCH`/`DUPLICATE_HISTORY`/`BALANCE_DISCONTINUITY` 异常检测。
- **规则引擎健壮性**：`rule_service` 的 `gte`/`lte` 操作符在字段为 `None` 时会抛 `InvalidOperation`（`balance` 等可选字段）。当前计划内规则只用 `contains`/`eq` 不触发；接入数值规则前需加 None 防护（TDD 补一个用例）。
- **前端分包**：AntD 整包打入单 chunk（~1MB）。需 `manualChunks` 或动态 import 拆分。
- **AntD message context**：使用了静态 `message` API，v5 会一次性警告；建议接入 `App` 组件的 `message` context。
- **审计 ip/UA**：当前 `ip_address`/`user_agent` 留空。需从 `Request` 提取。
- **金额模式**：`parser_service` 仅实现 `INCOME_EXPENSE_COLUMNS` 一种；enums 定义了 4 种（`SINGLE_AMOUNT_WITH_DIRECTION`/`DEBIT_CREDIT_COLUMNS`/`SIGNED_AMOUNT`），其余待补。
- **认证/权限**：MVP 无 auth，路由在 payload 里带 `user-1`。需补 JWT + RBAC（5 类角色：管理员/模板管理员/财务处理员/复核员/审计员）。
- **异步任务**：解析/规则匹配当前同步。大文件（>10000 行）需引入 Celery/RQ（技术设计已规划）。

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
