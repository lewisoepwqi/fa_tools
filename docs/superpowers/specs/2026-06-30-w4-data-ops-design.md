# 设计：数据运维（W4）

> 日期：2026-06-30 · 状态：自主模式产出（用户已授权「不逐项确认、自行决定」），待用户复核
> 范围：**W4** —— 迁移契约测试、PostgreSQL 实测基础设施、大文件解析/转换的鲁棒性与异步化基础。
> 前置：W0–W3、W5 均已合并到 main。

## 0. 定位与现状修正

W4 收口「数据运维」：锁住 schema 漂移、让 PG 能被真实验证、把大文件转换从「同步全量物化、失败即 500」改造为「有状态、可恢复、内存有界」。开工探查（对照代码）修正了两处过时认知：

- **P0-2 批次快照版本 ID 已实现**：`ConversionRun` 的 3 个版本 FK 列在 `run_conversion`（内联路径取 `payload.*_version_id`，`conversion_service.py:123-125`）与 `run_conversion_from_config`（版本驱动路径快照已保存版本，`:436-438`）均已赋值，导出/反查消费端已依赖。**W4 不含 P0-2。**
- **迁移契约已有半成品**：`tests/unit/test_migration_contract.py` 已建 upgrade-head/downgrade-base 框架 + 手写列断言，但**无 `compare_metadata` 自动比对**；且 `conftest.py` 用 `Base.metadata.create_all` 建表、**不跑迁移**——两条 schema 路径并存，漂移无守卫。这是 W4 要堵的核心裂缝。

## 1. 范围

### In（W4 做）
**A. 迁移契约（高价值、可立即测）**
1. `compare_metadata` autogenerate-no-diff 测试：在全新库 `upgrade head` 后，断言 `Base.metadata` 与迁移产出的 schema **零 diff**（env.py 已 import 工具层模型，metadata 完整）。锁死 create_all-vs-migration 漂移。

**B. PostgreSQL 实测基础设施（设计成「有 Docker 一键验证」+ CI 固化）**
2. `conftest.py` 改读 `settings.test_database_url`（现硬编码 SQLite）；新增「PG 实测」测试标记：`TEST_DATABASE_URL` 指向可达 PG 时运行、否则 `pytest.skip`（本地无 Docker 跳过、CI 起 PG 时实跑）。
3. `docker-compose.yml` postgres 加 `healthcheck`；新增 GitHub Actions CI（`.github/workflows/ci.yml`）：① SQLite 任务（永远跑全量 + ruff）；② PG 任务（`services: postgres`，跑 `alembic upgrade head` + 迁移契约 + 全量集成测试，真实验证 `server_default`/`Numeric(18,2)`/JSON 在 PG 行为）。
4. **JSON vs JSONB 决策**：探查确认**当前无任何 DB 层 JSON 查询**（`output_values`/审计 before-after 等都在 Python 层读）。依 YAGNI **保留通用 `JSON`**（PG 建为 `json`），不迁 `JSONB`——迁移会引入 PG 专属类型、复杂化 SQLite 契约测试，且无现实查询需求。在 `docs/` 记一份决策说明 + 未来引入 JSON 查询时迁 JSONB 的路径（dialect-aware 类型 + `USING col::jsonb` 迁移）。一键验证流程写入 `README`/`docs`。

**C. 大文件鲁棒性 + 异步基础（可立即测的部分做实，broker 依赖部分设计+文档）**
5. **转换状态机**：新增 `RunStatus` 枚举（`pending`/`processing`/`completed`/`failed`）；把 `run_conversion` 拆为 `create_pending_run`（建 run，status=pending）+ `process_conversion_run(db, run_id, ...)`（重活：解析/规则/落库，写 processing→completed；异常时写 `failed` + 错误摘要，不再整请求 500）。保留薄 `run_conversion` 同步组合二者，现有同步契约与 `dry-run` 不变。
6. **流式解析**：`parser_service._read_rows` 现把 XLSX/CSV **全量物化成 list**（`:481-484`），是大文件 OOM 真正根因。改为生成器/分块读取，使内存与文件大小解耦（这是「大文件」真正的修复，且与是否上 broker 无关、可测）。
7. **失败可观测**：`ConversionRun` 增 `error_message`（或复用 summary_json 存错误）；`failed` 批次详情可见错误原因。

### Out（W4 不做，显式排除 + 理由）
- **Celery/RQ 真异步 worker + `202 + 轮询` API + 前端轮询**：本环境**无 Docker/broker**，真异步既不可运行也不可验证；而 FastAPI `BackgroundTasks` 是**同进程**执行——对「大文件」不提供 worker 隔离/横向扩展，只换了 API 形状，却带来「POST 契约从 200-完整结果变 202-run_id」的大爆炸半径（冲击 `UploadPage` 内联展示 + 大量测试）。依「与 PG 同一模式：设计成有基础设施时一键落地、不在本地伪造」——**完整设计 + 文档化为生产 rollout**（§5），不在 W4 实装。状态机（C5）与流式（C6）已把 worker 接入变成「把 `process_conversion_run` 从 BackgroundTasks/同步改投递到 Celery」的小改动。**前端轮询亦随之推迟**（goal 明确「前端深度接入可留作后续」）。
- **去重哈希 / 余额连续性（P1-3）**：属解析/引擎层逻辑（`parser_service`/`conversion_service` 行级检测），非数据运维；handover 标非 MVP。W4 不含。
- **JSONB 迁移**：见 B4，YAGNI 推迟。

## 2. 后端改动

### 2.1 迁移契约测试（A1）
- `tests/unit/test_migration_contract.py` 增 `test_no_autogenerate_diff`：
  - 在临时 SQLite 文件库 `command.upgrade(cfg, "head")`（复用现有 `monkeypatch.setenv("DATABASE_URL")` + `get_settings.cache_clear()` 机制）。
  - `with engine.connect() as conn: MigrationContext.configure(conn, opts={"compare_type": True})`，`diffs = compare_metadata(ctx, Base.metadata)`，断言 `diffs == []`。
  - 失败信息打印 `diffs` 便于定位「模型改了没补迁移」。
- 这把「conftest create_all」与「迁移」两条路径用一个断言钉死：任何模型变更未补迁移 → 红。

### 2.2 conftest PG 可切换（B2）
- `_create_test_engine` 改为读 `get_settings().test_database_url`（默认仍 SQLite 内存）。SQLite 分支保持 `StaticPool` + FK pragma；非 SQLite（PG）分支用常规连接池、不挂 SQLite-only pragma。
- 新增 `pytest.mark.pg`（或基于 `TEST_DATABASE_URL` scheme 的 `skipif`）：标记需真实 PG 的测试（迁移契约可在两库都跑；PG 专属断言如 jsonb/类型仅 PG 跑）。本地无 PG → skip，不破坏现有 318 绿。

### 2.3 转换状态机 + 拆分（C5/C7）
- `app/tools/bank_journal/enums.py` 增 `RunStatus(str, Enum)`：`PENDING/PROCESSING/COMPLETED/FAILED`。
- `conversion_service.py`：
  - `create_pending_run(db, payload) -> ConversionRun`：建 run（status=PENDING）+ 关联 files，flush，**不解析**。
  - `process_conversion_run(db, run_id, upload_dir) -> ConversionRunResponse`：置 PROCESSING → 解析/规则/落库 preview rows → 成功置 COMPLETED + summary；**异常捕获置 FAILED + `error_message`**，不向上抛 500。
  - `run_conversion(db, payload, upload_dir)`：保持现签名/返回（同步组合 `create_pending_run` + `process_conversion_run`），现有路由/测试/`dry-run`/`from-config` 不变。
- `ConversionRun` 增 `error_message: Mapped[str | None]`（迁移 0006）。`failed` 批次详情/列表暴露该字段。
- **迁移**：新增 `0006_run_status_error.py`（加 `error_message` 列；status 既有列不变）。补 §2.1 契约测试覆盖新列。

### 2.4 流式解析（C6）
- `parser_service._read_rows`：CSV 用 `csv.reader` 迭代器（不 `splitlines()` 全量）；XLSX `iter_rows` 直接迭代不 `list(...)`。对外暴露行迭代器；上层 `parse_bank_rows` 按需消费。保持解析结果不变（纯重构 + 内存特性改善），既有解析单测护航。
- 注：表头检测需前 N 行——用「先读窗口、再链回剩余」的 `itertools.chain` 模式，避免重复全量读。

## 3. 模块边界与可测性

| 单元 | 职责 | 测试 |
|---|---|---|
| 迁移契约（A1） | upgrade head 后 metadata 零 diff | 单测：`compare_metadata([])`；改模型不补迁移→红 |
| conftest 切库（B2） | SQLite/PG 引擎按 settings 切换 | 现有 318 测试在 SQLite 仍绿；PG 标记本地 skip |
| CI（B3） | SQLite 任务 + PG service 任务 | workflow 文件；PG 任务跑迁移+契约+全量 |
| RunStatus + 拆分（C5） | pending→processing→completed/failed | 单测/集成：状态流转、失败置 FAILED+error_message 不 500 |
| 流式解析（C6） | 行迭代不全量物化 | 既有 parser 单测不回归；新增大文件不 OOM 行为（迭代器断言/计数） |

## 4. 执行顺序（TDD）
1. A1 迁移契约 `compare_metadata` 测试（先确认现状无 diff，钉死基线）。
2. B2 conftest 读 `test_database_url` + PG skip 标记（保持 SQLite 全绿）。
3. B3 docker-compose healthcheck + GitHub Actions CI（SQLite + PG service）。
4. B4 JSON/JSONB 决策文档 + 一键验证 runbook。
5. C5 RunStatus 枚举 + `create_pending_run`/`process_conversion_run` 拆分 + 失败置 FAILED + `error_message` 列 + 迁移 0006（并更新 A1 契约覆盖新列）。
6. C6 流式 `_read_rows` 重构。
7. C7 `failed` 批次错误暴露（详情/列表 schema 带 error_message）。

每任务门禁：`cd backend && .venv/bin/pytest -q` + `.venv/bin/python -m ruff check .` 全绿；涉及前端展示 `failed` 的最小改动加 `npm run build`。迁移改动（0006）属「改迁移」，提交前征求确认（用户已授权自主，但迁移单独标注）。

## 5. 异步生产 rollout（设计完成，W4 不实装，待 Docker/broker 环境）

W4 已把转换重活收敛为单一可投递单元 `process_conversion_run(db, run_id, upload_dir)`。生产异步化只需：
1. 引入 broker（Redis）+ Celery（或 RQ）；`docker-compose` 加 redis + worker 服务。
2. `POST /conversion-runs` 改为：`create_pending_run` 后**投递** `process_conversion_run.delay(run_id)`，立即返回 **202 + `{run_id, status: pending}`**。
3. 任务状态查询复用 `GET /conversion-runs/{run_id}`（已返回 `status`/`summary`/`error_message`）。
4. 前端 `UploadPage` 改为提交后**轮询** `GET run` 直至终态（completed/failed）再展示结果。
5. 测试用 Celery `task_always_eager=True`（同进程，无需 broker）覆盖投递→状态流转。
> 因 `process_conversion_run` 已是纯函数式重活单元且状态机就位，上述为「接线」级改动，无引擎/数据模型变更。本环境无 Docker/broker，故 W4 不实装（与 PG 实测同一处置：基础设施就绪即一键落地）。

## 6. 验收
- 后端 `pytest -q` 全绿（含迁移契约 `compare_metadata` 空 diff、RunStatus 流转、失败置 FAILED 不 500、流式解析不回归）；`ruff` 全绿。
- conftest 可经 `TEST_DATABASE_URL` 指向 PG 跑全量（CI PG 任务证明）；本地无 PG 时优雅 skip，SQLite 全绿不变。
- GitHub Actions：SQLite 任务 + PG 任务均绿（PG 任务真实跑迁移 + 契约 + 集成）。
- 迁移线性 0001→0006，`alembic upgrade head` 在 SQLite 与 PG 均成功；autogenerate 无 diff。
- 文档：JSON/JSONB 决策 + 有 Docker 的一键 PG 验证 runbook + 异步 rollout 设计齐备。

## 7. 跨工作流依赖
- 无下游工作流依赖 W4。W4 依赖 W5 已合并（基线 318 测试）。异步 rollout（§5）与 JSONB（B4）为 W4 之后的独立后续，均已文档化。
