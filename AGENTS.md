# AGENTS.md — FA Tools

财务自动化工具包（Financial automation tools）。每个财务工具是一个可独立挂载/卸载的模块，平台层只提供共享基础设施（DB、用户/公司/审计、文件上传、配置）。当前内置工具：银行流水转公司日记账。FastAPI 后端 + React 前端。

## 项目结构
- `backend/` — Python 3.12, FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + openpyxl
- `frontend/` — React 18 + TypeScript + Ant Design v5 + Vite
- `docs/` — PRD、技术设计、实施计划、验收清单

### 分层（平台共享层 vs 工具层）

**后端 `backend/app/`：**
- 平台共享层：`core/`（config、通用枚举）、`db/`（base/session）、`models/`（user/company/audit/file/common）、`services/`（audit_service/file_service）、`api/routes/`（files/audit）、`api/deps.py`
- 工具层：`tools/<tool>/`，每个工具一个子包。如 `tools/bank_journal/`（models/services/schemas/routes/`__init__`）

**前端 `frontend/src/`：**
- 平台共享层：`App.tsx`、`main.tsx`、`api/client.ts`、`api/files.ts`、`components/AppShell.tsx`、`pages/AuditLogPage.tsx`、`tools/registry.ts`
- 工具层：`tools/<tool>/`，如 `tools/bank_journal/`（pages/components/types/api/routes/`index.ts`）

### 新增一个财务工具

1. 后端：在 `backend/app/tools/<name>/` 下建 `models/ services/ schemas/ routes/`，在 `__init__.py` 暴露 `register(app)`，并在其 `models/__init__.py` 导入模型（触发注册到 `Base.metadata`）。然后在 `app/main.py` 调用其 `register(app)`，在 `migrations/env.py` 加 `import app.tools.<name>`。
2. 前端：在 `frontend/src/tools/<name>/` 下建页面/路由，在 `index.ts` 导出 `Tool` 描述符并加入 `tools/registry.ts`。菜单与路由即自动挂载，无需改 AppShell/App。
3. 工具专属路由前缀统一为 `/api/tools/<tool-id>/...`；平台共享路由（`/api/files`、`/api/audit-logs`）无前缀。

## 后端命令
```bash
# 测试（必须用 .venv 的 pytest；PEP 668 阻止系统 python）
cd backend && .venv/bin/pytest -q

# Lint（ruff 装在 ~/.local/bin，不在 .venv）
cd backend && ruff check .

# 启动开发服务器
cd backend && .venv/bin/uvicorn app.main:app --reload
```

## 前端命令
```bash
cd frontend && npm run build      # 构建（tsc -b && vite build）
cd frontend && npm run dev        # 开发服务器 http://localhost:5173
cd frontend && npm run e2e        # Playwright 冒烟（首次需 npx playwright install chromium）
```

## 测试数据库
- 测试用 SQLite in-memory（`backend/tests/conftest.py` override `get_db` + `Base.metadata.create_all`）。
- 生产用 PostgreSQL：`docker compose up -d postgres` + `cd backend && alembic upgrade head`。
- 当前环境**无 Docker**；PostgreSQL 实测留待后续环境。

## 约定
- Python 3.12，ruff 规则 `E,F,I,UP,B`，行长 100。
- Conventional commits（`feat:` / `fix:` / `chore:` / `docs:` / `test:`）。
- TDD：先写测试看失败，再实现。
- 版本化记录（模板/映射/规则）一经批次引用不可变；编辑创建新版本。
- 不确定项默认进入人工确认（保守）。
- 持久化：source_files → bank_transactions → journal_preview_rows → manual_adjustments/confirmations → exports，全链路 + audit_logs。
- 路径解析一律走 DB 元数据（防路径穿越）。

## 已知后续项（非 MVP）
见 `docs/mvp-acceptance-checklist.md`：PostgreSQL 实测、账号字段加密、去重哈希/余额连续性、前端 chunk 分包、审计 ip/UA 捕获。
