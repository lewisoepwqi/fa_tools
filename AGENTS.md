# AGENTS.md — FA Tools

银行流水转公司日记账工具。FastAPI 后端 + React 前端。

## 项目结构
- `backend/` — Python 3.12, FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + openpyxl
- `frontend/` — React 18 + TypeScript + Ant Design v5 + Vite
- `docs/` — PRD、技术设计、实施计划、验收清单

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
