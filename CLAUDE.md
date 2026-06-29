# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

FA Tools 是一个财务自动化工具包：FastAPI 后端 + React 前端。架构核心是**平台共享层 + 可插拔工具模块**——每个财务工具是一个独立挂载/卸载的子包，平台层只提供共享基础设施（DB、用户/公司/审计、文件上传、配置）。当前唯一工具：`bank_journal`（银行流水转公司日记账）。

> 另见 `AGENTS.md`（同等权威的协作约定）与 `.impeccable.md`（全站视觉设计基准，改它即改全站设计）。本文件不重复其细节。

## 命令

后端（注意：环境受 PEP 668 限制，必须用 `.venv` 里的可执行文件）：
```bash
cd backend && .venv/bin/pytest -q              # 全部测试
cd backend && .venv/bin/pytest tests/unit/test_parser_service.py -q          # 单个文件
cd backend && .venv/bin/pytest tests/unit/test_parser_service.py::test_name  # 单个用例
cd backend && ruff check .                      # lint（ruff 装在 ~/.local/bin，不在 .venv）
cd backend && .venv/bin/uvicorn app.main:app --reload   # 开发服务器
```

前端：
```bash
cd frontend && npm run dev     # 开发服务器 http://localhost:5173
cd frontend && npm run build   # tsc -b && vite build
cd frontend && npm run test    # vitest 单元测试
cd frontend && npm run e2e     # Playwright（首次需 npx playwright install chromium）
```

测试数据库用 SQLite in-memory（`tests/conftest.py` override `get_db`）；生产用 PostgreSQL（`docker compose up -d postgres` + `cd backend && alembic upgrade head`）。**当前环境无 Docker**，PostgreSQL 实测留待后续。

## 架构

### 平台共享层 vs 工具层

后端 `backend/app/`：
- 共享层：`core/`（config、enums）、`db/`（base/session）、`models/`（user/company/audit/file/common）、`services/`（audit/file）、`api/routes/`（files/audit）、`api/deps.py`
- 工具层：`tools/<tool>/`，每工具一个子包，内部分 `models/ services/ schemas/ routes/`

前端 `frontend/src/`：
- 共享层：`App.tsx`、`api/client.ts`、`components/AppShell.tsx`、`pages/AuditLogPage.tsx`、`tools/registry.ts`
- 工具层：`tools/<tool>/`，内部分 `pages/ components/ types/ api/ routes.tsx index.ts`

### 工具的自描述注册（关键机制）

前端工具是**自描述**的：`tools/<name>/index.ts` 导出一个 `Tool` 描述符（id、label、icon、basePath、Routes、children 子菜单），加入 `tools/registry.ts` 的 `registry` 数组后，AppShell 的侧边栏菜单与 App 的路由**自动挂载**，无需改 AppShell/App。

后端工具 `tools/<name>/__init__.py` 暴露 `register(app)` 把路由挂载到 FastAPI app。

### 新增一个财务工具的接线点

后端需改 **3 处**，前端 **1 处**：
1. `app/main.py` — 调用该工具的 `register(app)`
2. 工具的 `models/__init__.py` — 导入所有模型（触发注册到 `Base.metadata`），且 `__init__.py` 顶部 `import ... models`
3. `migrations/env.py` — `import app.tools.<name>`（让 Alembic autogenerate 看到表）
4. 前端 `tools/registry.ts` — 把工具描述符加入 `registry`

工具专属路由前缀统一 `/api/tools/<tool-id>/...`；平台共享路由（`/api/files`、`/api/audit-logs`）无前缀。

### bank_journal 数据流

全链路持久化 + 审计：`source_files → bank_transactions → journal_preview_rows → manual_adjustments/confirmations → exports`，每步写 `audit_logs`。配置（模板/映射/规则）与执行（conversion run）解耦——服务层按 `parser_service / mapping_service / rule_service / conversion_service / export_service` 划分。

## 项目约定

- **语言**：一律用中文——回复用户用中文，代码注释用中文，提交信息、文档用中文。仅技术术语（如类名、函数名、API、库名、`FastAPI`、`SQLAlchemy` 等专有名词）保留原文。
- Python 3.12，ruff 规则 `E,F,I,UP,B`，行长 100。
- Conventional commits（`feat:`/`fix:`/`chore:`/`docs:`/`test:`）；提交信息可用中文。
- TDD：先写测试看失败，再实现。
- **版本化记录不可变**：模板/映射/规则一经批次引用即不可改，编辑则创建新版本。
- 不确定项默认进入**人工确认**（保守优先于自动）。
- 文件路径解析一律走 DB 元数据（防路径穿越），不直接信任客户端传入路径。
- 界面以中文为主。视觉改动须遵循 `.impeccable.md`（中大咨询集团 VI：品牌红 `#b5141d`、品牌蓝 `#133f8e`、暖中性、楷体标题），在 Ant Design v5 之上叠加主题 token，不脱离 antd 另造组件。
