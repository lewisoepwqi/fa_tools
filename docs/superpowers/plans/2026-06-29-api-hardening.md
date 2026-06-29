# API 健壮性(W2)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把后端 API 契约与性能做到生产级:脏输入 422(非 500)、批次预览行分页、关键索引、消除 list N+1、缺文件 404、审计响应 schema 化。

**Architecture:** 新增类型化输入契约(`schemas/contracts.py`,判别联合 + 递归条件模型)在 API 边界校验,内部仍 `model_dump(by_alias=True)` 成 dict 喂给现有 domain/service(零业务改动)。新增 `Page[T]` 信封与 preview-rows 分页子端点;list 服务的逐父查最新版本改为单查询;模型加索引并配一个 Alembic 迁移。

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, ruff。

## Global Constraints

- 测试:`cd backend && .venv/bin/pytest`(venv python;PEP 668 阻止系统 python)。
- Lint:`cd backend && .venv/bin/ruff check .`(规则 E,F,I,UP,B;行长 100)。
- 提交:Conventional commits,结尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- **向后兼容硬约束**:现有 183 后端测试 + 7 前端 e2e 全程绿;`run_conversion_from_config` 历史路径不被新契约误拒;新契约模型必须接受所有现存合法配置形状(空 `{"all":[]}` 条件、`{target,type:"field",source}` 映射、`_advanced` 透传映射)。
- TDD:先红后绿再提交。Decimal 处理金额,禁 float。
- 鉴权/租户过滤/加密属 W3,**不在本计划**;审计只做 schema + 分页。

## 范围回顾(spec §1–§6)
类型化契约→422 · preview-rows 分页子端点(现有详情端点不变)· 索引+迁移 · 消除 4 个 list N+1 · 转换缺文件 404 · 审计响应 schema。扁平 list 分页留 W5。

## 文件结构

| 文件 | 职责 | 任务 |
|------|------|------|
| `schemas/pagination.py` | `Page[T]` 信封 | T1 |
| `schemas/contracts.py` | `LeafConditionIn`/`ConditionIn`/`MappingIn` 判别联合/`ActionIn`/`RuleIn` | T2 |
| `schemas/conversion.py` | `ConversionRunCreate` 用 contracts 类型;`BankParseConfig.amount_mode: AmountMode` | T3 |
| `services/conversion_service.py` | `run_conversion` 顶部 dump 契约;缺文件 404;`list_preview_rows` 分页查询 | T3,T4,T7 |
| `routes/conversion_runs.py` | preview-rows 分页子端点 | T4 |
| `models/conversion.py` 等版本模型 | `index=True` / 复合索引 | T5 |
| `migrations/versions/0004_add_indexes.py` | 索引迁移 | T5 |
| `services/template_service.py` / `mapping_service` 列表 / `rule` 列表服务 | N+1 → 单查询 | T6 |
| `app/schemas/audit.py` | `AuditLogResponse` | T8 |
| `app/api/routes/audit.py` | response_model + 分页 | T8 |

---

## Task 1: Page[T] 分页信封

**Files:**
- Create: `backend/app/tools/bank_journal/schemas/pagination.py`
- Test: `backend/tests/unit/test_pagination_schema.py`

**Interfaces:**
- Produces: `class Page(BaseModel, Generic[T])` 字段 `items: list[T]`、`total: int`、`limit: int`、`offset: int`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_pagination_schema.py
from pydantic import BaseModel

from app.tools.bank_journal.schemas.pagination import Page


class _Item(BaseModel):
    name: str


def test_page_envelope_serializes():
    page = Page[_Item](items=[_Item(name="a")], total=5, limit=2, offset=0)
    dumped = page.model_dump()
    assert dumped == {"items": [{"name": "a"}], "total": 5, "limit": 2, "offset": 0}


def test_page_empty():
    page = Page[_Item](items=[], total=0, limit=100, offset=0)
    assert page.items == [] and page.total == 0
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_pagination_schema.py -v`
Expected: FAIL(`ModuleNotFoundError ... schemas.pagination`)

- [ ] **Step 3: 实现**

```python
# backend/app/tools/bank_journal/schemas/pagination.py
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页信封:items 为当前页数据,total 为过滤后总数。"""

    items: list[T]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 4: 运行,确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_pagination_schema.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/schemas/pagination.py tests/unit/test_pagination_schema.py
git add app/tools/bank_journal/schemas/pagination.py tests/unit/test_pagination_schema.py
git commit -m "feat(bank-journal): 新增 Page[T] 分页信封

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 类型化输入契约 contracts.py(治本 #9 模型层)

**Files:**
- Create: `backend/app/tools/bank_journal/schemas/contracts.py`
- Test: `backend/tests/unit/test_contracts.py`

**Interfaces:**
- Consumes: `app.tools.bank_journal.enums.AmountMode`(仅参考;amount_mode 在 T3 用)
- Produces:
  - `LeafConditionIn(field: str, op: <Literal>, value: Any = None)`
  - `ConditionIn` —— 递归模型,恰好一种形态:`all: list[ConditionIn]` / `any: list[ConditionIn]` / `not_(alias "not"): ConditionIn` / 叶子(`field`+`op`+`value`);空 `{"all": []}` 合法
  - `ActionIn(field: str, value: Any = None)`
  - `RuleIn(id, version_id, priority: int, conditions: ConditionIn, actions: list[ActionIn], allow_auto_confirm: bool = False)`
  - `MappingIn` —— 按 `type` 判别联合:`FieldMapping/FixedMapping/RuleOutputMapping/ConcatMapping/ConditionalMapping/ManualMapping`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_contracts.py
import pytest
from pydantic import TypeAdapter, ValidationError

from app.tools.bank_journal.schemas.contracts import (
    ConditionIn,
    MappingIn,
    RuleIn,
)

_mapping_adapter = TypeAdapter(MappingIn)


def test_condition_accepts_nested_and_empty_all():
    # 嵌套 any/all 合法
    ConditionIn.model_validate({"any": [{"field": "summary", "op": "contains", "value": "工资"}]})
    # 空 all 合法(from-config 默认形状,运行期语义=不匹配,但结构合法)
    ConditionIn.model_validate({"all": []})


def test_condition_rejects_empty_and_unknown_op():
    with pytest.raises(ValidationError):
        ConditionIn.model_validate({})  # 零分支
    with pytest.raises(ValidationError):
        ConditionIn.model_validate({"field": "x", "op": "bogus", "value": 1})  # 非法操作符
    with pytest.raises(ValidationError):
        ConditionIn.model_validate({"field": "x"})  # 叶子缺 op


def test_rule_in_valid_and_missing_version_id():
    RuleIn.model_validate({
        "id": "r1", "version_id": "v1", "priority": 1,
        "conditions": {"all": [{"field": "summary", "op": "eq", "value": "x"}]},
        "actions": [{"field": "account", "value": "管理费用"}],
        "allow_auto_confirm": False,
    })
    with pytest.raises(ValidationError):
        RuleIn.model_validate({  # 缺 version_id
            "id": "r1", "priority": 1, "conditions": {"all": []}, "actions": [],
        })


def test_mapping_discriminated_union():
    _mapping_adapter.validate_python({"type": "field", "target": "科目", "source": "summary"})
    _mapping_adapter.validate_python({"type": "concat", "target": "摘要", "sources": ["a", "b"], "separator": "-"})
    _mapping_adapter.validate_python({"type": "fixed", "target": "币种", "value": "CNY"})
    with pytest.raises(ValidationError):
        _mapping_adapter.validate_python({"type": "bogus", "target": "x"})  # 未知 type
    with pytest.raises(ValidationError):
        _mapping_adapter.validate_python({"type": "field", "target": "x"})  # field 缺 source
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_contracts.py -v`
Expected: FAIL(`ModuleNotFoundError ... schemas.contracts`)

- [ ] **Step 3: 实现**

```python
# backend/app/tools/bank_journal/schemas/contracts.py
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 操作符集合对齐 domain/conditions.py 已实现的。
Operator = Literal[
    "eq", "ne", "contains", "not_contains", "contains_any", "in",
    "is_empty", "gte", "lte", "gt", "lt", "date_gte", "date_lte",
]


class LeafConditionIn(BaseModel):
    """叶子条件 {field, op, value}。conditional 映射的 condition 用它(运行期走 evaluate_leaf)。"""

    field: str
    op: Operator
    value: Any = None


class ConditionIn(BaseModel):
    """规则条件 AST 的输入校验:恰好一种形态(all / any / not / 叶子)。

    递归;空 {"all": []} 结构合法(from-config 默认),运行期语义由 domain 决定。
    """

    all: list["ConditionIn"] | None = None
    any: list["ConditionIn"] | None = None
    not_: "ConditionIn | None" = Field(default=None, alias="not")
    field: str | None = None
    op: Operator | None = None
    value: Any = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _exactly_one_form(self) -> "ConditionIn":
        branches = [
            self.all is not None,
            self.any is not None,
            self.not_ is not None,
            self.field is not None,
        ]
        if sum(branches) != 1:
            raise ValueError("condition 必须恰好是 all / any / not / 叶子(field) 之一")
        if self.field is not None and self.op is None:
            raise ValueError("叶子条件必须含 op")
        return self


class ActionIn(BaseModel):
    field: str
    value: Any = None


class RuleIn(BaseModel):
    id: str
    version_id: str
    priority: int
    conditions: ConditionIn
    actions: list[ActionIn]
    allow_auto_confirm: bool = False


class _MappingBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str


class FieldMapping(_MappingBase):
    type: Literal["field"]
    source: str


class FixedMapping(_MappingBase):
    type: Literal["fixed"]
    value: Any = None


class RuleOutputMapping(_MappingBase):
    type: Literal["rule_output"]
    source: str


class ConcatMapping(_MappingBase):
    type: Literal["concat"]
    sources: list[str]
    separator: str = ""


class ConditionalMapping(_MappingBase):
    type: Literal["conditional"]
    condition: LeafConditionIn
    then_value: Any = None
    else_value: Any = None


class ManualMapping(_MappingBase):
    type: Literal["manual"]


MappingIn = Annotated[
    Union[
        FieldMapping,
        FixedMapping,
        RuleOutputMapping,
        ConcatMapping,
        ConditionalMapping,
        ManualMapping,
    ],
    Field(discriminator="type"),
]
```

- [ ] **Step 4: 运行,确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_contracts.py -v`
Expected: PASS(4 passed)。若递归前向引用报错,在文件末尾加 `ConditionIn.model_rebuild()`。

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/schemas/contracts.py tests/unit/test_contracts.py
git add app/tools/bank_journal/schemas/contracts.py tests/unit/test_contracts.py
git commit -m "feat(bank-journal): 类型化输入契约 ConditionIn/MappingIn/RuleIn(#9 模型层)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 把契约接入 ConversionRunCreate + run_conversion(治本 #9 接线)

**Files:**
- Modify: `backend/app/tools/bank_journal/schemas/conversion.py`(`ConversionRunCreate.mappings/rules` 类型;`BankParseConfig.amount_mode: AmountMode`)
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(`run_conversion` 顶部把 payload.mappings/rules `model_dump(by_alias=True)` 成 dict 局部变量,替换后续 `payload.mappings`/`payload.rules` 用法)
- Test: `backend/tests/integration/test_conversion_api.py`

**Interfaces:**
- Consumes: `MappingIn`/`RuleIn`(T2)、`AmountMode`(enums)
- Produces: 脏 mappings/rules/amount_mode 输入 → 422;内部 dict 流不变

- [ ] **Step 1: 写失败测试**(读现有 `test_conversion_api.py` 复用其 fixture/payload 形状;断言脏输入 422)

```python
# 追加到 backend/tests/integration/test_conversion_api.py
def test_unknown_mapping_type_returns_422(client, seeded_run_payload):
    payload = seeded_run_payload
    payload["mappings"] = [{"type": "bogus", "target": "科目"}]
    resp = client.post("/api/tools/bank-journal/conversion-runs", json=payload)
    assert resp.status_code == 422


def test_invalid_amount_mode_returns_422(client, seeded_run_payload):
    payload = seeded_run_payload
    payload["bank_parse_config"]["amount_mode"] = "not_a_mode"
    resp = client.post("/api/tools/bank-journal/conversion-runs", json=payload)
    assert resp.status_code == 422


def test_rule_missing_version_id_returns_422(client, seeded_run_payload):
    payload = seeded_run_payload
    payload["rules"] = [{"id": "r1", "priority": 1, "conditions": {"all": []}, "actions": []}]
    resp = client.post("/api/tools/bank-journal/conversion-runs", json=payload)
    assert resp.status_code == 422
```

(若现有文件无 `seeded_run_payload` fixture,改用该文件已有的构造 run 的 fixture/辅助;关键是 POST 脏输入断言 422。)

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_conversion_api.py -k "422" -v`
Expected: FAIL(当前 `list[dict[str,Any]]` 不校验,脏输入走到服务层 500 而非 422)

- [ ] **Step 3: 实现**

(a) `schemas/conversion.py` 顶部加导入并改类型:
```python
from app.tools.bank_journal.enums import AmountMode  # 已有 ExceptionCode/PreviewStatus 导入,补 AmountMode
from app.tools.bank_journal.schemas.contracts import MappingIn, RuleIn
```
把 `BankParseConfig.amount_mode: str` 改为 `amount_mode: AmountMode`。
把 `ConversionRunCreate` 的:
```python
    mappings: list[MappingIn]
    rules: list[RuleIn]
```

(b) `services/conversion_service.py` 的 `run_conversion`:在函数体最前(`run = ConversionRun(...)` 之前)加:
```python
    # 契约模型 → dict,喂给现有 domain/service(by_alias 还原 not_→not)。
    mappings = [m.model_dump(by_alias=True) for m in payload.mappings]
    rules = [r.model_dump(by_alias=True) for r in payload.rules]
```
然后把该函数内后续所有 `payload.mappings` 改为 `mappings`、`payload.rules` 改为 `rules`(包括 `for rule in payload.rules:` 的循环、`build_preview_row(transaction, payload.mappings, payload.rules, ...)` 调用)。`amount_mode = AmountMode(config.amount_mode)` 保持可用(`AmountMode(已是枚举)` 返回自身)。

- [ ] **Step 4: 运行,确认通过 + 全量回归(尤其 from_config)**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 新增 3 个 422 PASS;全量 PASS。**若 `test_conversion_from_config` / `test_full_mvp_flow` 失败**,说明某现存合法配置形状被契约误拒 —— 读失败信息,放宽对应模型(如某 mapping 形状未被联合覆盖、或 ConditionIn 误拒某结构),而非改测试。

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/schemas/conversion.py app/tools/bank_journal/services/conversion_service.py tests/integration/test_conversion_api.py
git add app/tools/bank_journal/schemas/conversion.py app/tools/bank_journal/services/conversion_service.py tests/integration/test_conversion_api.py
git commit -m "feat(bank-journal): 转换入参类型化校验,脏输入 422(#9)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: preview-rows 分页子端点

**Files:**
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(新增 `list_preview_rows`)
- Modify: `backend/app/tools/bank_journal/routes/conversion_runs.py`(新增路由 + import)
- Test: `backend/tests/integration/test_conversion_api.py`

**Interfaces:**
- Consumes: `Page`(T1)、`JournalPreviewRowData`、`_preview_row_to_data`(conversion_service 已有,JournalPreviewRow→JournalPreviewRowData)、`JournalPreviewRow` 模型
- Produces: `list_preview_rows(db, run_id: str, limit: int, offset: int) -> Page[JournalPreviewRowData]`;路由 `GET /api/tools/bank-journal/conversion-runs/{run_id}/preview-rows`

- [ ] **Step 1: 写失败测试**(基于现有 fixture 跑一个真实批次,断言分页)

```python
# 追加到 backend/tests/integration/test_conversion_api.py
def test_preview_rows_pagination(client, seeded_run_payload):
    run = client.post("/api/tools/bank-journal/conversion-runs", json=seeded_run_payload).json()
    run_id = run["id"]
    full = client.get(f"/api/tools/bank-journal/conversion-runs/{run_id}/preview-rows?limit=1&offset=0")
    assert full.status_code == 200
    body = full.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["limit"] == 1 and body["offset"] == 0
    assert len(body["items"]) <= 1
    assert body["total"] >= len(body["items"])


def test_preview_rows_limit_capped_at_500(client, seeded_run_payload):
    run = client.post("/api/tools/bank-journal/conversion-runs", json=seeded_run_payload).json()
    resp = client.get(
        f"/api/tools/bank-journal/conversion-runs/{run['id']}/preview-rows?limit=9999"
    )
    assert resp.status_code == 422  # 超过上限 500 由 Query(le=500) 拦截
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_conversion_api.py -k preview_rows -v`
Expected: FAIL(端点不存在 → 404)

- [ ] **Step 3: 实现**

(a) `services/conversion_service.py` 新增(放在 `get_conversion_run` 附近,复用已有 `_preview_row_to_data`):
```python
def list_preview_rows(
    db: Session, run_id: str, limit: int, offset: int
) -> Page[JournalPreviewRowData]:
    base = db.query(JournalPreviewRow).filter(JournalPreviewRow.conversion_run_id == run_id)
    total = base.count()
    rows = (
        base.order_by(JournalPreviewRow.row_index).offset(offset).limit(limit).all()
    )
    return Page[JournalPreviewRowData](
        items=[_preview_row_to_data(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
```
并在该文件顶部确保导入 `from app.tools.bank_journal.schemas.pagination import Page`(若未导入)。`Session`、`JournalPreviewRow`、`JournalPreviewRowData`、`_preview_row_to_data` 已在该模块可用。

(b) `routes/conversion_runs.py`:在 import 区加 `from fastapi import APIRouter, Query`,把 `list_preview_rows` 加进 `from ...conversion_service import (...)`,加 `from app.tools.bank_journal.schemas.pagination import Page`,`from app.tools.bank_journal.schemas.conversion import JournalPreviewRowData`,然后新增路由(放在 `get_run` 之后):
```python
@router.get("/{run_id}/preview-rows", response_model=Page[JournalPreviewRowData])
def list_run_preview_rows(
    db: DbSession,
    run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[JournalPreviewRowData]:
    """分页返回某批次的日记账预览行,按 row_index 升序。"""
    return list_preview_rows(db, run_id, limit, offset)
```

- [ ] **Step 4: 运行,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 新增 2 测试 PASS;全量 PASS。

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/services/conversion_service.py app/tools/bank_journal/routes/conversion_runs.py tests/integration/test_conversion_api.py
git add app/tools/bank_journal/services/conversion_service.py app/tools/bank_journal/routes/conversion_runs.py tests/integration/test_conversion_api.py
git commit -m "feat(bank-journal): 新增 preview-rows 分页子端点

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 关键索引 + Alembic 迁移

**Files:**
- Modify: `backend/app/tools/bank_journal/models/conversion.py`(给 `*_run_id`、`row_hash` 加 `index=True`;`conversion_runs.company_id` 加 `index=True`)
- Modify: 版本模型文件(`models/template.py`、`models/mapping.py`、`models/rule.py`)加 `(parent_id, version_no)` 复合索引(`__table_args__`)
- Create: `backend/migrations/versions/0004_add_indexes.py`
- Test: `backend/tests/unit/test_indexes.py`

**Interfaces:**
- Produces: 上述列/复合索引;可逆迁移 `0004_add_indexes`(down_revision = `"0003_builtin_field_overrides"`)

- [ ] **Step 1: 写失败测试**(用 SQLAlchemy inspect 在 create_all 后断言索引存在)

```python
# backend/tests/unit/test_indexes.py
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import audit, company, file, user  # noqa: F401
from app.tools.bank_journal import models  # noqa: F401


def _indexed_columns(insp, table):
    cols = set()
    for ix in insp.get_indexes(table):
        cols.update(tuple(ix["column_names"]) if len(ix["column_names"]) > 1 else ix["column_names"])
    return cols


def test_hot_path_indexes_present():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    # 预览行/交易按 run 过滤
    assert "conversion_run_id" in _indexed_columns(insp, "journal_preview_rows")
    assert "conversion_run_id" in _indexed_columns(insp, "bank_transactions")
    # 去重历史查询热点
    assert "row_hash" in _indexed_columns(insp, "bank_transactions")
    # 版本表复合索引(parent_id, version_no)其一列出现即可
    assert ("bank_template_id", "version_no") in _indexed_columns(insp, "bank_template_versions")
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_indexes.py -v`
Expected: FAIL(索引未定义)

- [ ] **Step 3: 实现**

(a) `models/conversion.py`:给以下列加 `index=True`(在对应 `mapped_column(...)` 内补参数):
- `JournalPreviewRow.conversion_run_id`、`BankTransaction.conversion_run_id`、`ConversionRunFile.conversion_run_id`、`ConversionRunRuleVersion.conversion_run_id`
- `BankTransaction.row_hash`
- `ConversionRun.company_id`
例如 `conversion_run_id: Mapped[str] = mapped_column(ForeignKey("conversion_runs.id"), nullable=False, index=True)`。

(b) 各版本模型加复合索引。以 `models/template.py` 的 `BankTemplateVersion` 为例,在类体加:
```python
from sqlalchemy import Index
# 类体内:
    __table_args__ = (
        Index("ix_bank_template_versions_parent_ver", "bank_template_id", "version_no"),
    )
```
对 `CompanyJournalTemplateVersion`(parent fk 名以模型为准)、`mapping_profile_versions`、`rule_versions` 同样添加,索引名各自唯一(`ix_<table>_parent_ver`)。READ 每个版本模型确认其父外键列名后再写。

(c) 迁移 `backend/migrations/versions/0004_add_indexes.py`:
```python
"""add hot-path indexes

Revision ID: 0004_add_indexes
Revises: 0003_builtin_field_overrides
"""
from alembic import op

revision = "0004_add_indexes"
down_revision = "0003_builtin_field_overrides"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_journal_preview_rows_run", "journal_preview_rows", ["conversion_run_id"]),
    ("ix_bank_transactions_run", "bank_transactions", ["conversion_run_id"]),
    ("ix_bank_transactions_row_hash", "bank_transactions", ["row_hash"]),
    ("ix_conversion_run_files_run", "conversion_run_files", ["conversion_run_id"]),
    ("ix_conversion_run_rule_versions_run", "conversion_run_rule_versions", ["conversion_run_id"]),
    ("ix_conversion_runs_company", "conversion_runs", ["company_id"]),
    ("ix_bank_template_versions_parent_ver", "bank_template_versions", ["bank_template_id", "version_no"]),
    ("ix_company_journal_template_versions_parent_ver", "company_journal_template_versions", ["company_journal_template_id", "version_no"]),
    ("ix_mapping_profile_versions_parent_ver", "mapping_profile_versions", ["mapping_profile_id", "version_no"]),
    ("ix_rule_versions_parent_ver", "rule_versions", ["rule_id", "version_no"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
```
**注意**:迁移里的表名/列名必须与实际模型一致 —— 实现前 READ 各版本模型确认父外键列名(如 `company_journal_template_id`、`mapping_profile_id`、`rule_id`),不一致则改正。索引名要与 (b) 中模型 `__table_args__` 的名字一致,避免 autogenerate 漂移。

- [ ] **Step 4: 运行,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 新增索引测试 PASS;全量 PASS(create_all 带索引不影响现有用例)。

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/models tests/unit/test_indexes.py migrations/versions/0004_add_indexes.py
git add app/tools/bank_journal/models migrations/versions/0004_add_indexes.py tests/unit/test_indexes.py
git commit -m "perf(bank-journal): 热点路径索引 + Alembic 迁移 0004

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 消除 4 个 list 端点的 N+1

**Files:**
- Modify: `backend/app/tools/bank_journal/services/template_service.py`(`list_bank_templates`、`list_journal_templates`)
- Modify: mapping 列表服务、rule 列表服务(`list_mapping_profiles` / `list_rules` 所在文件 —— 实现前 grep 确认是在 service 还是 route 内联)
- Test: `backend/tests/integration/test_list_filtering.py`(已存在;断言结果与改前一致)

**Interfaces:**
- Produces: list 服务用单查询取各父最新版本(group-by max(version_no) 连表),结果与逐父查询一致

- [ ] **Step 1: 确认回归基线(本任务是行为不变的内部优化)**

本任务把"逐父查最新版本"改为"单查询",**对外行为完全不变** —— 回归护栏是现有
`tests/integration/test_list_filtering.py` 与各 `test_versioning_endpoints.py`(它们已断言
列表/详情返回最新版本)。先读 `tests/integration/test_list_filtering.py` 与
`tests/integration/test_versioning_endpoints.py`,确认其中确有"创建新版本后,列表项反映最新
version_no"的断言。

- 若**已覆盖**:不新增测试;本任务以"改造后这些现有用例仍全绿"为验收(Step 4)。
- 若**未覆盖**该断言:在 `test_list_filtering.py` 用该文件**真实的**创建辅助函数补一条:
  建一个模板 → 为它创建第 2 个版本 → 调列表端点 → 断言该模板项的 `version_no`(或版本相关字段)
  等于最新版本。用文件里实际的辅助名与响应字段,写成完整可运行的断言(不留占位符)。

- [ ] **Step 2: 运行(基线)**

Run: `cd backend && .venv/bin/pytest tests/integration/test_list_filtering.py -v`
Expected: 现有用例 PASS(作为改造前基线;若新增了断言且它依赖尚未优化的代码,应仍 PASS,因为行为不变)。

- [ ] **Step 3: 实现**(以 `list_bank_templates` 为样板,其余三处同构)

把 `template_service.list_bank_templates` 的逐父循环换成单查询:
```python
from sqlalchemy import func

def list_bank_templates(db: Session, company_id: str | None = None) -> list[BankTemplateResponse]:
    query = db.query(BankTemplate)
    if company_id is not None:
        query = query.filter(BankTemplate.company_id == company_id)
    query = query.filter(BankTemplate.status != RecordStatus.DELETED.value)
    parents = query.all()
    if not parents:
        return []
    parent_ids = [p.id for p in parents]
    # 每个父的最新 version_no
    latest_no = (
        db.query(
            BankTemplateVersion.bank_template_id.label("pid"),
            func.max(BankTemplateVersion.version_no).label("mv"),
        )
        .filter(BankTemplateVersion.bank_template_id.in_(parent_ids))
        .group_by(BankTemplateVersion.bank_template_id)
        .subquery()
    )
    versions = (
        db.query(BankTemplateVersion)
        .join(
            latest_no,
            (BankTemplateVersion.bank_template_id == latest_no.c.pid)
            & (BankTemplateVersion.version_no == latest_no.c.mv),
        )
        .all()
    )
    by_parent = {v.bank_template_id: v for v in versions}
    return [_bank_template_to_response(p, by_parent.get(p.id)) for p in parents]
```
对 `list_journal_templates`、mapping 列表、rule 列表用同样模式(替换父/版本模型与外键列名)。**实现前 READ 这四个列表函数**确认各自的父模型、版本模型、外键列名、`_to_response` 辅助名。

- [ ] **Step 4: 运行,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全量 PASS,列表结果与改前一致。

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/services/template_service.py app/tools/bank_journal/services tests/integration/test_list_filtering.py
git add app/tools/bank_journal/services tests/integration/test_list_filtering.py
git commit -m "perf(bank-journal): list 端点消除 N+1,单查询取最新版本

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 转换缺文件返回 404

**Files:**
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(`run_conversion` 与 `dry_run_conversion` 解析前检查文件存在)
- Test: `backend/tests/integration/test_conversion_api.py`

**Interfaces:**
- Produces: source file 记录存在但磁盘缺失 → `HTTPException(404)`(非 500)

- [ ] **Step 1: 写失败测试**

关键:必须测"**DB 有 SourceFile 行、但磁盘无文件**"这条新路径 —— 不能用"不存在的 source_file_id"
(那会命中**已有的** "source file not found" 404,即使没改代码也通过,是假测试)。用 W0+W1 已加的
`client_with_db` fixture(返回 `(TestClient, Session)`,见 `tests/conftest.py`)直接插入一条
`SourceFile` 行,其 `storage_key` 指向一个不存在的文件,再 POST 转换。

```python
# 追加到 backend/tests/integration/test_conversion_api.py
from uuid import uuid4

from app.models.file import SourceFile  # 路径以实际模型为准


def test_conversion_missing_disk_file_returns_404(client_with_db, seeded_run_payload):
    test_client, db = client_with_db
    sf_id = str(uuid4())
    db.add(SourceFile(
        id=sf_id,
        company_id=seeded_run_payload["company_id"],
        # 其余必填列以 SourceFile 模型为准(uploaded_by/original_filename/file_type/storage_key/...)
        original_filename="ghost.csv",
        file_type="csv",
        storage_key=f"{sf_id}.csv",   # 磁盘上不存在
    ))
    db.commit()
    payload = dict(seeded_run_payload)
    payload["source_file_ids"] = [sf_id]
    resp = test_client.post("/api/tools/bank-journal/conversion-runs", json=payload)
    assert resp.status_code == 404
```
实现前 READ `app/models/file.py::SourceFile` 补齐所有 NOT NULL 列(如 `uploaded_by`、`file_size`、
`status` 等),保证插入成功。断言 404(新检查命中),而非 500。

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_conversion_api.py -k missing_disk -v`
Expected: 当前若 source 行存在但文件缺失 → `parse_bank_rows` 抛错未捕获 → 500(FAIL)。

- [ ] **Step 3: 实现**

在 `run_conversion` 里(`file_path = upload_dir / source.storage_key` 之后、`parse_bank_rows(file_path, ...)` 之前)加:
```python
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source file missing on disk: {source_file_id}",
            )
```
在 `dry_run_conversion` 的相应解析位置加同样检查。确保 `HTTPException`、`status` 已在该模块导入(已用于现有 source-not-found 404,应已导入)。

- [ ] **Step 4: 运行,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 新增 404 测试 PASS;全量 PASS。

- [ ] **Step 5: 提交**

```bash
cd backend && .venv/bin/ruff check app/tools/bank_journal/services/conversion_service.py tests/integration/test_conversion_api.py
git add app/tools/bank_journal/services/conversion_service.py tests/integration/test_conversion_api.py
git commit -m "fix(bank-journal): 转换缺磁盘文件返回 404 非 500

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 审计响应 schema + 分页

**Files:**
- Create: `backend/app/schemas/audit.py`
- Modify: `backend/app/api/routes/audit.py`
- Test: `backend/tests/unit/test_audit_service.py` 或新增 `backend/tests/integration/test_audit_api.py`

**Interfaces:**
- Consumes: `Page`(T1)、`AuditLog` 模型
- Produces: `AuditLogResponse` 模型;`GET /api/audit-logs?limit&offset` → `Page[AuditLogResponse]`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_audit_api.py
def test_audit_logs_paged_and_typed(client):
    resp = client.get("/api/audit-logs?limit=5&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["limit"] == 5 and body["offset"] == 0
    # 每条结构符合 AuditLogResponse 的键
    for item in body["items"]:
        assert {"id", "action", "entity_type", "entity_id", "created_at"} <= set(item)


def test_audit_logs_limit_cap(client):
    resp = client.get("/api/audit-logs?limit=9999")
    assert resp.status_code == 422
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_audit_api.py -v`
Expected: FAIL(当前返回裸 list,无 items/total;limit 不被校验)

- [ ] **Step 3: 实现**

(a) `backend/app/schemas/audit.py`:
```python
from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    company_id: str | None = None
    actor_id: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    before_json: dict[str, Any] | None = None
    after_json: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: str | None = None
```
(字段名/可空性以 `app/models/audit.py` 的 `AuditLog` 为准 —— 实现前 READ 确认。)

(b) `app/api/routes/audit.py` 改为:
```python
from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.tools.bank_journal.schemas.pagination import Page

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogResponse])
def list_audit_logs(
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Page[AuditLogResponse]:
    base = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    total = base.count()
    rows = base.offset(offset).limit(limit).all()
    items = [
        AuditLogResponse(
            id=r.id,
            company_id=r.company_id,
            actor_id=r.actor_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            before_json=r.before_json,
            after_json=r.after_json,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    return Page[AuditLogResponse](items=items, total=total, limit=limit, offset=offset)
```

- [ ] **Step 4: 运行,确认通过 + 全量 + lint**

Run: `cd backend && .venv/bin/pytest -q && .venv/bin/ruff check .`
Expected: 全量 PASS;ruff 干净。

- [ ] **Step 5: 提交**

```bash
git add app/schemas/audit.py app/api/routes/audit.py tests/integration/test_audit_api.py
git commit -m "feat: 审计端点强类型响应 + 分页

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 收尾:全量验证
- [ ] `cd backend && .venv/bin/pytest -q`(全绿)、`.venv/bin/ruff check .`(干净)。
- [ ] `cd frontend && npm run build && npm run e2e`(7/7 绿 —— 确认未破坏 API 契约形状:现有详情/list 端点未改、审计页用 mock 数据不受影响)。
- [ ] 对照 spec §9 验收清单逐条确认。

## 自检:spec 覆盖映射
| spec 验收项 | 任务 |
|------|------|
| 脏 mappings/rules/amount_mode → 422 | T2(模型)+ T3(接线) |
| from_config 历史路径不被误拒 | T3 Step 4 回归 |
| preview-rows 分页端点(items/total/limit/offset,limit≤500) | T1 + T4 |
| 4 个 list 消除 N+1,结果一致 | T6 |
| 关键索引 + 可逆迁移 | T5 |
| 转换缺文件 404 | T7 |
| 审计强类型响应 + 分页 | T1 + T8 |
| 现有 183 + 7 e2e 全绿 + 新用例 | 各任务 Step 4 + 收尾 |

> 范围外(后续):W3 鉴权/租户/加密/审计脱敏/FK pragma · W4 迁移真实执行+契约/PG/异步 · W5 前端分页接入/扁平 list 分页/动态列。
