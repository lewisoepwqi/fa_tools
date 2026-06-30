# 数据运维 Runbook

> 日期：2026-06-30  
> 涵盖：PostgreSQL 验证、JSON/JSONB 决策、CI 自动化、异步生产 rollout 指引

---

## 1. JSON vs JSONB 决策

### 现状

所有 `*_json` 列（`output_values_json`、`before_state`、`after_state` 等）目前使用通用 SQLAlchemy `JSON` 类型，在 PostgreSQL 中建为 `json` 类型（不是 `JSONB`）。此设计保证 SQLite 兼容性。

### 决策依据（YAGNI）

**当前无任何 DB 层 JSON 查询需求**：
- `output_values` 的异常码解析在 Python 层读取
- 审计日志的 `before_state`/`after_state` 对比在应用层处理
- `summary_json` 的统计计数在应用层编排

因此，依 **You Aren't Gonna Need It** 原则，**保留通用 `JSON` 类型**，不迁 `JSONB`。迁移会引入 PostgreSQL 专属类型、复杂化 SQLite 契约测试，且当前无现实收益。

### 未来迁 JSONB 路径（当引入 JSON 字段查询时）

若未来需支持以下场景，则重新评估 JSONB：
- 审计日志按 JSON key 过滤（如「查所有改过 account_no 的记录」）
- 预览行按 exception code 查询
- preview_rows 的 `output_values` 按特定键检索

**迁 JSONB 的步骤**（已验证）：

1. **定义 dialect-aware 类型**（在 `app/db/base.py` 中）：
   ```python
   from sqlalchemy import JSON as GenericJSON
   from sqlalchemy.dialects.postgresql import JSON as PostgresJSON, JSONB

   JSONType = GenericJSON().with_variant(JSONB(), "postgresql")
   ```

2. **替换所有 `*_json` 列**：
   ```python
   output_values_json: Mapped[dict] = mapped_column(JSONType, default=dict)
   ```

3. **创建迁移**：
   ```python
   # 迁移 0007_jsonb_migration.py
   def upgrade() -> None:
       op.execute("ALTER TABLE journal_preview_rows ALTER COLUMN output_values_json TYPE jsonb USING output_values_json::jsonb;")
       op.execute("ALTER TABLE audit_logs ALTER COLUMN before_state TYPE jsonb USING before_state::jsonb;")
       # ... 其他列
       op.create_index(
           "ix_audit_logs_before_state_keys",
           "audit_logs",
           postgresql_using="gin",
           postgresql_ops={"before_state": "jsonb_path_ops"}
       )
   ```

4. **验证**：
   ```bash
   cd backend
   .venv/bin/alembic upgrade head
   .venv/bin/pytest -q -m pg  # PostgreSQL 特定测试
   ```

> SQLite 无 JSONB 概念，上述迁移在 SQLite 上仍为 no-op；契约测试会因 SQLite 与 PG 类型不同而报 diff，此时可在测试中按 dialect 排除 JSONB 类型差异的断言。

---

## 2. PostgreSQL 一键验证（Docker 环境）

### 前置检查

- 已安装 Docker 与 Docker Compose
- 后端 `.venv` 已激活
- 数据库默认凭证未改（见下方说明）

### 一键验证流程

**步骤 1：启动 PostgreSQL 16 服务**

```bash
docker compose up -d postgres
# 验证服务已启动（含 healthcheck）
docker compose ps postgres
# 预期：STATUS 显示 "healthy"
```

**步骤 2：运行迁移**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools \
  .venv/bin/alembic upgrade head
```

预期输出：无错，显示 `INFO [alembic.runtime.migration] Running upgrade ... to ...`，迁移线性 `0001 → 0006`。

**步骤 3：运行迁移契约测试**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools \
  .venv/bin/pytest tests/unit/test_migration_contract.py -q
```

验证点：
- `upgrade head` 后，元数据与 SQLAlchemy 模型零 diff（`compare_metadata` 断言）
- `server_default` 在 PG 语义正确（如 `status = 'COMPLETED'` 默认值）
- `Numeric(18, 2)` 精度验证（不会 float 浮点误差）
- `JSON` 列在 PG 被正确映射为 `json` 类型

**步骤 4：运行全量测试套件（PostgreSQL 后端）**

```bash
TEST_DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools \
  .venv/bin/pytest -q
```

预期：全部测试绿（包括 SQLite 相关和 PG 相关的全部测试）。

**步骤 5：清理**

```bash
docker compose down
# 若要完全清理卷
docker compose down -v
```

### 数据库凭证说明

当前 `docker-compose.yml` 使用：
- **用户**：`fa_tools`
- **密码**：`fa_tools`
- **数据库**：`fa_tools`
- **主机**：`localhost:5432`

> 生产部署时需通过环境变量覆盖，见 `docs/handover.md` §12「生产部署须知」。

### 故障排查

| 问题 | 排查步骤 |
|---|---|
| `psycopg.OperationalError: connection failed` | `docker compose ps postgres` 检查容器状态；`docker compose logs postgres` 查日志 |
| `UNIQUE constraint violation` | 上次测试未清理（脏数据）；运行 `docker compose down -v` 重置数据库 |
| 迁移卡顿 | 检查 `alembic.ini` 的 `sqlalchemy.url` 是否被环境变量覆盖；用 `echo $DATABASE_URL` 验证 |
| 类型不匹配（如 NUMERIC 精度） | 检查迁移是否真实运行（而非 create_all 偷工）；`docker compose exec postgres psql ... -l` 查 schema 版本号 |

---

## 3. CI 固化（GitHub Actions）

### 配置

见 `.github/workflows/ci.yml`（已配置）：

**SQLite 任务**（每次 push/PR 自动跑）：
```yaml
backend-sqlite:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: cd backend && pip install -e . && .venv/bin/pytest -q
    - run: cd backend && .venv/bin/python -m ruff check .
```

**PostgreSQL 任务**（同上，额外启动 PG 服务）：
```yaml
backend-pg:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_USER: fa_tools
        POSTGRES_PASSWORD: fa_tools
        POSTGRES_DB: fa_tools
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
      ports:
        - 5432:5432
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: |
        cd backend
        DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools \
          .venv/bin/alembic upgrade head
    - run: |
        cd backend
        TEST_DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools \
          .venv/bin/pytest -q
```

### 验证要点

CI 中 PG 任务验证：
1. ✅ 迁移在 PostgreSQL 16 上无误（`alembic upgrade head` exit 0）
2. ✅ `server_default` 行为正确
3. ✅ `Numeric(18, 2)` 精度无误
4. ✅ `JSON` 列在 PG 建为 `json` 类型
5. ✅ 迁移契约 `compare_metadata` 零 diff（钉死 schema 漂移）
6. ✅ 全量集成测试在 PG 环境绿（包括文件上传、转换、导出）

### 本地复现 CI

```bash
# 若本地无 Docker，所有测试仍在 SQLite 跑，PG 测试优雅 skip
cd backend && .venv/bin/pytest -q

# 若本地有 Docker，可手动复现 PG 任务
docker compose up -d postgres
TEST_DATABASE_URL=postgresql+psycopg://fa_tools:fa_tools@localhost:5432/fa_tools \
  .venv/bin/pytest -q
docker compose down
```

---

## 4. 异步生产 Rollout 指引

### 设计概述

见 `docs/superpowers/specs/2026-06-30-w4-data-ops-design.md` §5 详细设计。核心理念：

**当前架构**（同步）：
```
POST /api/conversion-runs
  ├─ create_pending_run(db, payload)  # 建 run 元数据
  ├─ process_conversion_run(db, run_id, ...)  # 同步解析/规则/落库
  └─ return ConversionRunResponse  # 200 + 完整结果
```

**异步化后**（需 broker）：
```
POST /api/conversion-runs
  ├─ create_pending_run(db, payload)  # 建 run，status=PENDING
  ├─ 投递 process_conversion_run.delay(run_id) 到消息队列
  └─ return 202 + {run_id, status: PENDING}  # 立即返回，后台处理

GET /api/conversion-runs/{run_id}
  └─ return {status: PROCESSING/COMPLETED/FAILED, summary, error_message}  # 轮询获取进度
```

### 前置条件

- ✅ 已有 `RunStatus` 枚举：`PENDING / PROCESSING / COMPLETED / FAILED`
- ✅ 已有状态机：`create_pending_run` → `process_conversion_run` → 置 COMPLETED/FAILED
- ✅ 已有失败兜底：异常捕获置 `FAILED + error_message`，不向上抛 500
- ✅ 已有流式解析：大文件不 OOM
- ✅ `ConversionRun.error_message` 列已就绪

### 一键落地步骤（当有 Docker 及 broker 环境时）

#### 1. 引入 broker 与异步框架

```bash
# 添加 Python 依赖（pyproject.toml）
dependencies = [
    ...
    "celery[redis]>=5.3",  # 或 "rq"
]

# 启动 Redis 服务（docker-compose.yml）
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  celery:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    depends_on:
      - redis
      - postgres
```

#### 2. 配置 Celery 应用

```python
# app/celery_app.py
from celery import Celery
from app.core.config import get_settings

settings = get_settings()
app = Celery(
    "fa_tools",
    broker=settings.celery_broker_url,  # redis://localhost:6379/0
    backend=settings.celery_result_backend,
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
)

@app.task(bind=True)
def process_conversion_run_async(self, run_id: str, upload_dir: str):
    """由 worker 异步执行的转换任务"""
    from sqlalchemy import create_engine
    from app.db.session import get_db
    from app.tools.bank_journal.services.conversion_service import process_conversion_run
    
    engine = create_engine(settings.database_url)
    with SessionLocal(bind=engine)() as db:
        try:
            return process_conversion_run(db, run_id, upload_dir)
        except Exception as e:
            self.retry(exc=e, countdown=60, max_retries=3)
```

#### 3. 修改转换路由

```python
# app/tools/bank_journal/routes/conversion_runs.py
from app.celery_app import process_conversion_run_async

@router.post("/conversion-runs", response_model=ConversionRunResponse)
def create_conversion_run(
    payload: ConversionRunPayload,
    db: Session = Depends(get_db),
    upload_dir: str = Depends(get_upload_dir),
):
    """创建转换批次并投递异步任务"""
    # 建 run 元数据
    run = create_pending_run(db, payload)
    db.commit()
    
    # 投递异步任务
    process_conversion_run_async.delay(run.id, upload_dir)
    
    # 立即返回 202 + run_id
    return JSONResponse(
        status_code=202,
        content={
            "run_id": run.id,
            "status": "PENDING",
            "message": "Conversion queued. Poll GET /api/conversion-runs/{run_id} for progress.",
        }
    )
```

#### 4. 暴露 status 与 error_message

```python
# schemas (ConversionRunResponse 增字段)
class ConversionRunResponse(BaseModel):
    id: str
    status: str  # PENDING / PROCESSING / COMPLETED / FAILED
    summary: dict
    error_message: str | None  # 失败原因
    created_at: datetime
```

#### 5. 前端轮询

```typescript
// frontend/src/tools/bank_journal/pages/UploadPage.tsx
const [runId, setRunId] = useState<string | null>(null);
const [status, setStatus] = useState<string>("IDLE");

const handleSubmit = async () => {
  const response = await conversionRunsApi.create(payload);
  setRunId(response.run_id);
  setStatus("PENDING");
  // 轮询 GET /api/conversion-runs/{run_id}
  pollConversionStatus(response.run_id);
};

const pollConversionStatus = (id: string) => {
  const interval = setInterval(async () => {
    const run = await conversionRunsApi.get(id);
    setStatus(run.status);
    
    if (run.status === "COMPLETED") {
      clearInterval(interval);
      message.success("转换完成");
      // 跳转到详情页
    } else if (run.status === "FAILED") {
      clearInterval(interval);
      message.error(`转换失败：${run.error_message}`);
    }
  }, 1000);  // 每秒轮询
};
```

#### 6. 测试

```python
# 配置 Celery eager 模式（同进程执行，便于测试）
@pytest.fixture
def celery_config():
    return {
        "task_always_eager": True,
        "task_eager_propagates": True,
    }

# 测试用例不变，Celery 会同步执行 delay() 调用
def test_conversion_run_async(db, client):
    response = client.post("/api/conversion-runs", json=payload)
    assert response.status_code == 202
    
    # 立即轮询（Celery eager 已同步执行）
    run_id = response.json()["run_id"]
    response = client.get(f"/api/conversion-runs/{run_id}")
    assert response.json()["status"] == "COMPLETED"
```

### 验证清单

部署前逐项验证：

- [ ] Redis 服务已启动 (`docker compose ps redis`)
- [ ] Celery worker 已启动 (`celery -A app.celery_app worker` 进程存活)
- [ ] `POST /api/conversion-runs` 返回 202 + run_id
- [ ] `GET /api/conversion-runs/{run_id}` 返回 status 流转（PENDING → PROCESSING → COMPLETED/FAILED）
- [ ] 任务异常被捕获，`error_message` 可见，不返回 500
- [ ] 前端轮询逻辑正确（已清理之前的同步等待代码）
- [ ] 全量测试在 `task_always_eager=True` 下仍绿
- [ ] 性能基准：大文件（>10000 行）处理不阻塞主线程

### 回滚方案

若异步化遇到线上问题：

1. **临时禁用 Celery**：
   ```python
   # settings 增 ENABLE_ASYNC=False
   if settings.enable_async:
       process_conversion_run_async.delay(run_id, upload_dir)
   else:
       # 同步降级
       process_conversion_run(db, run_id, upload_dir)
   ```

2. **保留同步路由**：`run_conversion` 仍可调用，用于 `dry-run` 或紧急处理

3. **监控任务队列**：
   ```bash
   # Celery 提供 flower UI
   pip install flower
   celery -A app.celery_app flower
   # 访问 http://localhost:5555 查看任务、重试、失败情况
   ```

---

## 附录：本地开发查询

### 何时需要实施本 runbook

- ✅ 一键验证 PG 环境（无 Docker 跳过 PG 部分，SQLite 始终可测）
- ✅ 本地引入 JSON 查询或需 JSONB 性能优化时参考 §1
- ✅ 生产部署前运行 §2 完整验证
- ✅ CI 已固化（§3），本地提交会触发
- ✅ 引入 Celery 或其他 broker 时参考 §4

### 常见问题

**Q: 本地无 Docker，能验证 PostgreSQL 吗？**  
A: 不能。此时 SQLite in-memory 测试仍全绿。若无 Docker 环境，可跳过 §2 PG 一键验证；生产或 CI 环境必须补全。

**Q: 现在就想用 JSONB，需要改什么？**  
A: 参考 §1「未来迁 JSONB 路径」，需修改 4 处：类型定义 + 所有 `*_json` 列 + 迁移 + 迁移契约测试。但当前无查询需求，不建议提前。

**Q: 异步化会影响现有 API 契约吗？**  
A: 会。`POST /conversion-runs` 从 200 + 完整结果改为 202 + run_id。建议用特性开关 (`ENABLE_ASYNC`) 灰度。

**Q: 流式解析后，大文件能处理多大？**  
A: 取决于 broker 与 worker 内存。理论上内存与文件大小解耦；实际受 Python 进程内对象数量限制（规则/映射缓存、preview rows 对象）。建议监控 worker 内存使用，必要时加分页处理。

