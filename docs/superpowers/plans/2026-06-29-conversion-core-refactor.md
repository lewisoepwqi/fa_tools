# 转换核心重构(W0+W1)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入纯领域层(求值上下文 / 条件 AST / 金额值对象),修复转换链路的财务正确性 bug,并把解析做到生产级健壮。

**Architecture:** 新增 `app/tools/bank_journal/domain/`(无 DB/IO 的纯模块)承载核心逻辑;`services/` 退化为调用 domain 的薄编排层。规则/映射统一经 `EvaluationContext` 读取字段(标准 + 自定义同权),条件统一经 `evaluate()`(支持 all/any/not),金额统一经 `SignedAmount`(方向与符号恒一致)。

**Tech Stack:** Python 3.14(运行)/ 3.12+ 目标, FastAPI, SQLAlchemy 2, Pydantic v2, openpyxl, pytest, ruff。

## Global Constraints

- 测试命令一律用 venv 内可执行文件:`cd backend && .venv/bin/pytest`(PEP 668 阻止系统 python)。
- Lint:`cd backend && ruff check .`,规则 `E,F,I,UP,B`,行长 100。
- 提交信息用 Conventional commits(中文正文可),结尾加:`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- **向后兼容硬约束**:现有 138 后端测试 + 7 前端 e2e 全程保持绿;历史批次 `output_values_json`/`*_version` 快照只读不动;旧配置 `conditions_json={"all":[...]}` 必须继续工作。
- TDD:每个功能先写失败测试,看红,再实现,看绿,再提交。
- 金额一律 `Decimal`,禁止 float 参与金额计算。
- 不新增第三方依赖(编码探测用 stdlib 回退,不引 chardet)。

## 范围与排期说明

- 本计划仅 W0+W1。spec §2.3 的**类型化 Rule/Mapping 输入契约(`contracts.py`)推迟到 W2**——它的价值(入参 422)在 W2 与 `ConversionRunCreate` 一起接线时才实现,在此提前定义会是未使用代码(YAGNI)。W0 交付运行期校验的 `evaluate()` 与值对象,已足以修复实际 bug。
- `conditional` 映射类型与 `gte/lte/date_gte/date_lte` 操作符**现已存在**,本计划是把它们迁到 domain 并经统一上下文求值,而非新增。

## 文件结构

| 文件 | 职责 | 任务 |
|------|------|------|
| `backend/app/tools/bank_journal/domain/__init__.py` | 包标记 | T1 |
| `backend/app/tools/bank_journal/domain/amounts.py` | `SignedAmount` 值对象 + 工厂 | T1 |
| `backend/app/tools/bank_journal/domain/fields.py` | `FieldType`/`FieldDef`/`EvaluationContext`(拍平扩展字段) | T2 |
| `backend/app/tools/bank_journal/domain/conditions.py` | 条件 AST `evaluate()`(all/any/not + 操作符) | T3 |
| `backend/app/tools/bank_journal/services/rule_service.py` | 改为调用 domain | T4 |
| `backend/app/tools/bank_journal/services/mapping_service.py` | 改为调用 domain | T5 |
| `backend/app/tools/bank_journal/schemas/standard.py` | 更正写反的注释 | T5 |
| `backend/app/tools/bank_journal/services/parser_service.py` | 编码探测 / 金额清洗 / SignedAmount / date 类型 | T7–T10 |
| `backend/app/tools/bank_journal/services/conversion_service.py` | 逐行错误隔离 / row_hash / 去重 / 余额 | T10–T13 |
| `backend/tests/unit/test_*.py` | 各任务单测 | 全部 |

---

## Task 1: SignedAmount 金额值对象(治本 #4)

**Files:**
- Create: `backend/app/tools/bank_journal/domain/__init__.py`(空文件)
- Create: `backend/app/tools/bank_journal/domain/amounts.py`
- Test: `backend/tests/unit/test_domain_amounts.py`

**Interfaces:**
- Consumes: `app.tools.bank_journal.enums.TransactionDirection`
- Produces:
  - `class AmountError(ValueError)`
  - `@dataclass(frozen=True) class SignedAmount` 字段 `magnitude: Decimal`(恒 ≥0)、`direction: TransactionDirection`、`sign_anomaly: bool=False`
  - 属性 `net_amount: Decimal`、`debit_amount: Decimal|None`、`credit_amount: Decimal|None`
  - 类方法 `from_income_expense(income, expense)`、`from_debit_credit(debit, credit)`、`from_amount_with_direction(amount, direction)`、`from_signed(amount)`,均返回 `SignedAmount`,无法定方向/双栏冲突时抛 `AmountError`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_domain_amounts.py
from decimal import Decimal

import pytest

from app.tools.bank_journal.domain.amounts import AmountError, SignedAmount
from app.tools.bank_journal.enums import TransactionDirection


def test_income_credit_positive():
    sa = SignedAmount.from_income_expense(Decimal("100"), None)
    assert sa.direction == TransactionDirection.CREDIT
    assert sa.net_amount == Decimal("100")
    assert sa.credit_amount == Decimal("100")
    assert sa.debit_amount is None
    assert sa.sign_anomaly is False


def test_expense_debit_negative_net():
    sa = SignedAmount.from_income_expense(None, Decimal("80"))
    assert sa.direction == TransactionDirection.DEBIT
    assert sa.net_amount == Decimal("-80")
    assert sa.debit_amount == Decimal("80")


def test_negative_income_flips_direction_and_flags_anomaly():
    # 收入栏填负数(冲账)→ 方向翻成借,magnitude 取绝对值,net 与方向一致,且标记异常
    sa = SignedAmount.from_income_expense(Decimal("-50"), None)
    assert sa.direction == TransactionDirection.DEBIT
    assert sa.magnitude == Decimal("50")
    assert sa.net_amount == Decimal("-50")
    assert sa.sign_anomaly is True


def test_both_columns_populated_raises():
    with pytest.raises(AmountError):
        SignedAmount.from_income_expense(Decimal("1"), Decimal("2"))


def test_signed_amount_factory():
    assert SignedAmount.from_signed(Decimal("-5")).direction == TransactionDirection.DEBIT
    assert SignedAmount.from_signed(Decimal("5")).direction == TransactionDirection.CREDIT
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_amounts.py -v`
Expected: FAIL(`ModuleNotFoundError: app.tools.bank_journal.domain.amounts`)

- [ ] **Step 3: 实现**

先建空包文件 `backend/app/tools/bank_journal/domain/__init__.py`(内容为空),再写:

```python
# backend/app/tools/bank_journal/domain/amounts.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.tools.bank_journal.enums import TransactionDirection

_ZERO = Decimal("0")


class AmountError(ValueError):
    """金额无法确定方向或双栏冲突。继承 ValueError 以兼容现有 except 捕获。"""


@dataclass(frozen=True)
class SignedAmount:
    magnitude: Decimal  # 恒 >= 0
    direction: TransactionDirection
    sign_anomaly: bool = False  # 原始值为负导致方向翻转,供上层标记 AMOUNT_DIRECTION_MISMATCH

    @property
    def net_amount(self) -> Decimal:
        return self.magnitude if self.direction == TransactionDirection.CREDIT else -self.magnitude

    @property
    def debit_amount(self) -> Decimal | None:
        return self.magnitude if self.direction == TransactionDirection.DEBIT else None

    @property
    def credit_amount(self) -> Decimal | None:
        return self.magnitude if self.direction == TransactionDirection.CREDIT else None

    @classmethod
    def _normalize(cls, value: Decimal, base: TransactionDirection) -> SignedAmount:
        if value < _ZERO:
            flipped = (
                TransactionDirection.DEBIT
                if base == TransactionDirection.CREDIT
                else TransactionDirection.CREDIT
            )
            return cls(magnitude=-value, direction=flipped, sign_anomaly=True)
        return cls(magnitude=value, direction=base)

    @classmethod
    def from_income_expense(
        cls, income: Decimal | None, expense: Decimal | None
    ) -> SignedAmount:
        inc = income or _ZERO
        exp = expense or _ZERO
        if inc != _ZERO and exp != _ZERO:
            raise AmountError("Both income and expense amounts are populated")
        if inc != _ZERO:
            return cls._normalize(inc, TransactionDirection.CREDIT)
        if exp != _ZERO:
            return cls._normalize(exp, TransactionDirection.DEBIT)
        raise AmountError("Unable to determine transaction amount")

    @classmethod
    def from_debit_credit(cls, debit: Decimal | None, credit: Decimal | None) -> SignedAmount:
        deb = debit or _ZERO
        cre = credit or _ZERO
        if deb != _ZERO and cre != _ZERO:
            raise AmountError("Both debit and credit amounts are populated")
        if cre != _ZERO:
            return cls._normalize(cre, TransactionDirection.CREDIT)
        if deb != _ZERO:
            return cls._normalize(deb, TransactionDirection.DEBIT)
        raise AmountError("Unable to determine transaction amount")

    @classmethod
    def from_amount_with_direction(
        cls, amount: Decimal, direction: TransactionDirection
    ) -> SignedAmount:
        return cls(magnitude=abs(amount), direction=direction)

    @classmethod
    def from_signed(cls, amount: Decimal) -> SignedAmount:
        if amount >= _ZERO:
            return cls(magnitude=amount, direction=TransactionDirection.CREDIT)
        return cls(magnitude=-amount, direction=TransactionDirection.DEBIT)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_amounts.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/domain tests/unit/test_domain_amounts.py
git add app/tools/bank_journal/domain/__init__.py app/tools/bank_journal/domain/amounts.py tests/unit/test_domain_amounts.py
git commit -m "feat(bank-journal): SignedAmount 值对象,方向与符号恒一致(#4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: EvaluationContext 求值上下文(治本 #2 地基)

**Files:**
- Create: `backend/app/tools/bank_journal/domain/fields.py`
- Test: `backend/tests/unit/test_domain_fields.py`

**Interfaces:**
- Consumes: `app.tools.bank_journal.schemas.standard.StandardBankTransaction`
- Produces:
  - `class FieldType(StrEnum)`:`STRING/DECIMAL/DATE/BOOL`
  - `@dataclass(frozen=True) class FieldDef`:`key: str`、`type: FieldType`、`origin: str`
  - `class EvaluationContext`:`.get(key)->Any`、`.has(key)->bool`、`.as_dict()->dict`、类方法 `from_transaction(txn)->EvaluationContext`(把 `extra_fields` 拍平进顶层命名空间)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_domain_fields.py
from decimal import Decimal

from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.enums import TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def _txn(**overrides):
    base = dict(
        transaction_date="2026-01-01",
        bank_account_id="acc-1",
        direction=TransactionDirection.CREDIT,
        net_amount=Decimal("100"),
        extra_fields={"cost_center": "CC-01"},
        source_file_id="f-1",
        source_sheet_name="Sheet1",
        source_row_index=2,
        raw_row={},
    )
    base.update(overrides)
    return StandardBankTransaction(**base)


def test_standard_field_accessible():
    ctx = EvaluationContext.from_transaction(_txn())
    assert ctx.get("net_amount") == Decimal("100")
    assert ctx.has("direction") is True


def test_custom_field_flattened_to_top_level():
    # 治本 #2:扩展字段与标准字段同权,直接用 field_key 取到
    ctx = EvaluationContext.from_transaction(_txn())
    assert ctx.get("cost_center") == "CC-01"
    assert ctx.has("cost_center") is True
    assert "extra_fields" not in ctx.as_dict()


def test_missing_field_returns_none():
    ctx = EvaluationContext.from_transaction(_txn())
    assert ctx.get("nonexistent") is None
    assert ctx.has("nonexistent") is False
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_fields.py -v`
Expected: FAIL(`ModuleNotFoundError ... domain.fields`)

- [ ] **Step 3: 实现**

```python
# backend/app/tools/bank_journal/domain/fields.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.tools.bank_journal.schemas.standard import StandardBankTransaction


class FieldType(StrEnum):
    STRING = "string"
    DECIMAL = "decimal"
    DATE = "date"
    BOOL = "bool"


@dataclass(frozen=True)
class FieldDef:
    key: str
    type: FieldType
    origin: str  # "standard" | "custom"


class EvaluationContext:
    """规则/映射引擎读取字段的统一上下文。

    标准字段与公司级自定义字段(extra_fields)拍平进单一命名空间,
    使二者在条件/映射中以相同方式被 field_key 引用(治本 #2)。
    """

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get(self, key: str) -> Any:
        return self._values.get(key)

    def has(self, key: str) -> bool:
        return key in self._values

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)

    @classmethod
    def from_transaction(cls, txn: StandardBankTransaction) -> EvaluationContext:
        data = txn.model_dump()
        extra = data.pop("extra_fields", None) or {}
        data.update(extra)  # 关键:扩展字段提到顶层,与标准字段同权
        return cls(data)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_fields.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/domain/fields.py tests/unit/test_domain_fields.py
git add app/tools/bank_journal/domain/fields.py tests/unit/test_domain_fields.py
git commit -m "feat(bank-journal): EvaluationContext 拍平扩展字段进统一命名空间(#2 地基)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 条件 AST evaluate()(治本 #1)

**Files:**
- Create: `backend/app/tools/bank_journal/domain/conditions.py`
- Test: `backend/tests/unit/test_domain_conditions.py`

**Interfaces:**
- Consumes: `EvaluationContext`(T2)
- Produces:
  - `def evaluate(node: dict, ctx: EvaluationContext) -> bool` —— 支持 `{"all":[...]}`/`{"any":[...]}`/`{"not":{...}}`/叶子 `{"field","op","value"}`;空 `{}` 视为匹配(向后兼容);未知结构抛 `ValueError`
  - 操作符:`eq ne contains contains_any not_contains gte lte gt lt date_gte date_lte in is_empty`
  - `def evaluate_leaf(cond: dict, ctx: EvaluationContext) -> bool`(供 mapping 的 conditional 复用)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_domain_conditions.py
from decimal import Decimal

import pytest

from app.tools.bank_journal.domain.conditions import evaluate
from app.tools.bank_journal.domain.fields import EvaluationContext


def _ctx(**vals):
    return EvaluationContext(dict(vals))


def test_all_is_and():
    ctx = _ctx(summary="工资", net_amount=Decimal("100"))
    node = {"all": [
        {"field": "summary", "op": "contains", "value": "工资"},
        {"field": "net_amount", "op": "gte", "value": "50"},
    ]}
    assert evaluate(node, ctx) is True


def test_any_is_or_not_ignored():
    # 治本 #1:any 必须按 OR 工作,而非被忽略
    ctx = _ctx(summary="报销")
    node = {"any": [
        {"field": "summary", "op": "contains", "value": "工资"},
        {"field": "summary", "op": "contains", "value": "报销"},
    ]}
    assert evaluate(node, ctx) is True


def test_not_node():
    ctx = _ctx(summary="工资")
    node = {"not": {"field": "summary", "op": "contains", "value": "报销"}}
    assert evaluate(node, ctx) is True


def test_custom_field_condition():
    # 治本 #2:扩展字段作为条件字段
    ctx = _ctx(cost_center="CC-01")
    node = {"all": [{"field": "cost_center", "op": "eq", "value": "CC-01"}]}
    assert evaluate(node, ctx) is True


def test_empty_conditions_match_all_backcompat():
    assert evaluate({}, _ctx()) is True
    assert evaluate({"all": []}, _ctx()) is True


def test_unknown_structure_raises_not_match_all():
    with pytest.raises(ValueError):
        evaluate({"weird": []}, _ctx())
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_conditions.py -v`
Expected: FAIL(`ModuleNotFoundError ... domain.conditions`)

- [ ] **Step 3: 实现**(操作符逻辑迁自 `rule_service._match_condition`,字段取值改走 `ctx.get`)

```python
# backend/app/tools/bank_journal/domain/conditions.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.tools.bank_journal.domain.fields import EvaluationContext


def evaluate(node: dict[str, Any], ctx: EvaluationContext) -> bool:
    if not isinstance(node, dict):
        raise ValueError(f"Invalid condition node: {node!r}")
    if not node:
        return True  # 无条件 = 匹配全部(向后兼容旧空配置)
    if "all" in node:
        return all(evaluate(child, ctx) for child in node["all"])
    if "any" in node:
        return any(evaluate(child, ctx) for child in node["any"])
    if "not" in node:
        return not evaluate(node["not"], ctx)
    if "field" in node:
        return evaluate_leaf(node, ctx)
    raise ValueError(f"Unsupported condition structure: {sorted(node)}")


def evaluate_leaf(cond: dict[str, Any], ctx: EvaluationContext) -> bool:
    actual = ctx.get(cond["field"])
    expected = cond.get("value")
    op = cond["op"]
    if hasattr(actual, "value"):  # 枚举取标量
        actual = actual.value

    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "contains":
        return str(expected) in str(actual or "")
    if op == "not_contains":
        return str(expected) not in str(actual or "")
    if op == "contains_any":
        return any(str(item) in str(actual or "") for item in expected or [])
    if op == "in":
        return actual in (expected or [])
    if op == "is_empty":
        return actual is None or str(actual) == ""
    if op in ("gte", "lte", "gt", "lt"):
        a = _decimal_or_none(actual)
        e = _decimal_or_none(expected)
        if a is None or e is None:
            return False
        return {"gte": a >= e, "lte": a <= e, "gt": a > e, "lt": a < e}[op]
    if op in ("date_gte", "date_lte"):
        a = _date_or_none(actual)
        e = _date_or_none(expected)
        if a is None or e is None:
            return False
        return a >= e if op == "date_gte" else a <= e
    raise ValueError(f"Unsupported rule operator: {op}")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    try:
        return Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return None


def _date_or_none(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_conditions.py -v`
Expected: PASS(6 passed)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/domain/conditions.py tests/unit/test_domain_conditions.py
git add app/tools/bank_journal/domain/conditions.py tests/unit/test_domain_conditions.py
git commit -m "feat(bank-journal): 条件 AST evaluate 支持 all/any/not(#1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: rule_service 改用 domain(治本 #1#2 落到规则链路)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/rule_service.py`(替换 `_matches`/`_match_condition`,保留 `apply_rules` 签名)
- Test: `backend/tests/unit/test_rule_service.py`(新增 2 个回归断言)

**Interfaces:**
- Consumes: `evaluate`(T3)、`EvaluationContext`(T2)
- Produces:`apply_rules(transaction, rules)` 签名不变;内部经统一上下文与 AST 求值

- [ ] **Step 1: 写失败测试**(追加到现有文件末尾)

```python
# 追加到 backend/tests/unit/test_rule_service.py
from decimal import Decimal

from app.tools.bank_journal.enums import TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.rule_service import apply_rules


def _txn(summary="报销款", extra=None):
    return StandardBankTransaction(
        transaction_date="2026-01-01",
        bank_account_id="acc-1",
        direction=TransactionDirection.DEBIT,
        net_amount=Decimal("-50"),
        summary=summary,
        extra_fields=extra or {},
        source_file_id="f-1",
        source_sheet_name="S",
        source_row_index=2,
        raw_row={},
    )


def test_any_rule_matches_via_or():
    rules = [{
        "id": "r1", "version_id": "v1", "priority": 1, "allow_auto_confirm": False,
        "conditions": {"any": [
            {"field": "summary", "op": "contains", "value": "工资"},
            {"field": "summary", "op": "contains", "value": "报销"},
        ]},
        "actions": [{"field": "account", "op": "set", "value": "管理费用"}],
    }]
    result = apply_rules(_txn(summary="报销款"), rules)
    assert result.outputs.get("account") == "管理费用"


def test_custom_field_rule_condition_matches():
    rules = [{
        "id": "r1", "version_id": "v1", "priority": 1, "allow_auto_confirm": False,
        "conditions": {"all": [{"field": "cost_center", "op": "eq", "value": "CC-01"}]},
        "actions": [{"field": "account", "op": "set", "value": "研发费用"}],
    }]
    result = apply_rules(_txn(extra={"cost_center": "CC-01"}), rules)
    assert result.outputs.get("account") == "研发费用"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_rule_service.py -k "any_rule or custom_field_rule" -v`
Expected: FAIL(`test_any_rule_matches_via_or`:`any` 当前被忽略 → outputs 为空;`test_custom_field_rule_condition_matches`:扩展字段取不到 → 不匹配)

- [ ] **Step 3: 实现**——替换 `rule_service.py` 顶部 import 与 `_matches`,删除 `_match_condition`/`_decimal_or_none`/`_date_or_none`(逻辑已迁入 domain)

把第 1–9 行的 import 段改为:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.tools.bank_journal.domain.conditions import evaluate
from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.enums import ExceptionCode
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
```

把第 58 行起的 `_matches` 及其后全部辅助函数(`_match_condition`/`_decimal_or_none`/`_date_or_none`)整段替换为:

```python
def _matches(transaction: StandardBankTransaction, conditions: dict[str, Any]) -> bool:
    ctx = EvaluationContext.from_transaction(transaction)
    return evaluate(conditions, ctx)
```

(`apply_rules` 主体不变,仍调用 `_matches(transaction, rule["conditions"])`。)

- [ ] **Step 4: 运行测试,确认通过 + 全量回归**

Run: `cd backend && .venv/bin/pytest tests/unit/test_rule_service.py -v && .venv/bin/pytest -q`
Expected: 新增 2 测试 PASS;全量 140 passed(原 138 + 2)。若 `mapping_service` 报 `ImportError: cannot import name '_match_condition'`,留待 T5 修复——本步可先单独跑 `test_rule_service.py` 确认绿,再进 T5。

> 注:`mapping_service.py` 当前 `from ... rule_service import _match_condition`。删除该函数会使其导入失败,故 **T4 与 T5 是连续的**,T5 完成后再跑全量。本步只需 `test_rule_service.py` 绿即可提交。

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/rule_service.py tests/unit/test_rule_service.py
git add app/tools/bank_journal/services/rule_service.py tests/unit/test_rule_service.py
git commit -m "refactor(bank-journal): rule_service 改用 domain 条件 AST + 上下文(#1#2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: mapping_service 改用 domain + 更正注释(治本 #2 落到映射链路)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/mapping_service.py`
- Modify: `backend/app/tools/bank_journal/schemas/standard.py:27-28`(更正写反的注释)
- Test: `backend/tests/unit/test_mapping_service.py`(新增断言)

**Interfaces:**
- Consumes: `EvaluationContext`(T2)、`evaluate_leaf`(T3)
- Produces:`apply_mappings(transaction, mappings, rule_outputs)` 签名不变;`field`/`concat` 来源可为扩展字段;`conditional` 经 `evaluate_leaf`

- [ ] **Step 1: 写失败测试**(追加)

```python
# 追加到 backend/tests/unit/test_mapping_service.py
from decimal import Decimal

from app.tools.bank_journal.enums import TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction
from app.tools.bank_journal.services.mapping_service import apply_mappings


def _txn(extra=None):
    return StandardBankTransaction(
        transaction_date="2026-01-01",
        bank_account_id="acc-1",
        direction=TransactionDirection.CREDIT,
        net_amount=Decimal("100"),
        summary="货款",
        extra_fields=extra or {},
        source_file_id="f-1",
        source_sheet_name="S",
        source_row_index=2,
        raw_row={},
    )


def test_custom_field_as_mapping_source():
    # 治本 #2:扩展字段作为映射来源不再抛错,而是取到值
    mappings = [{"target": "部门", "type": "field", "source": "cost_center"}]
    out = apply_mappings(_txn(extra={"cost_center": "CC-01"}), mappings, {})
    assert out["部门"] == "CC-01"


def test_conditional_mapping_still_works():
    mappings = [{
        "target": "类别", "type": "conditional",
        "condition": {"field": "summary", "op": "contains", "value": "货款"},
        "then_value": "营业收入", "else_value": "其他",
    }]
    out = apply_mappings(_txn(), mappings, {})
    assert out["类别"] == "营业收入"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_mapping_service.py -k "custom_field_as_mapping or conditional_mapping_still" -v`
Expected: FAIL(`test_custom_field_as_mapping_source`:`source not in transaction_data` 抛 ValueError;且当前从 `rule_service` 导入 `_match_condition` 已失效)

- [ ] **Step 3: 实现**——整体替换 `mapping_service.py`

```python
# backend/app/tools/bank_journal/services/mapping_service.py
from typing import Any

from app.tools.bank_journal.domain.conditions import evaluate_leaf
from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def apply_mappings(
    transaction: StandardBankTransaction,
    mappings: list[dict[str, Any]],
    rule_outputs: dict[str, Any],
) -> dict[str, Any]:
    ctx = EvaluationContext.from_transaction(transaction)
    mapped_values: dict[str, Any] = {}

    for mapping in mappings:
        target = mapping["target"]
        mapping_type = mapping.get("type")

        if mapping_type == "field":
            source = mapping.get("source")
            if not isinstance(source, str) or not ctx.has(source):
                raise ValueError(f"Unknown field mapping source for target {target}: {source}")
            value = ctx.get(source)
        elif mapping_type == "fixed":
            value = mapping.get("value")
        elif mapping_type == "rule_output":
            value = rule_outputs.get(mapping.get("source"))
        elif mapping_type == "concat":
            separator = mapping.get("separator", "")
            parts = []
            for source in mapping.get("sources", []):
                if not isinstance(source, str) or not ctx.has(source):
                    raise ValueError(
                        f"Unknown concat mapping source for target {target}: {source}"
                    )
                source_value = ctx.get(source)
                if source_value is not None and source_value != "":
                    parts.append(str(source_value))
            value = separator.join(parts)
        elif mapping_type == "conditional":
            condition = mapping.get("condition", {})
            value = (
                mapping.get("then_value")
                if evaluate_leaf(condition, ctx)
                else mapping.get("else_value")
            )
        elif mapping_type == "manual":
            value = None
        else:
            raise ValueError(f"Unsupported mapping type: {mapping_type}")

        mapped_values[target] = value

    return mapped_values
```

更正 `schemas/standard.py` 第 27–28 行注释:

```python
    # 公司级自定义扩展字段:field_key → 值。
    # 经 EvaluationContext.from_transaction() 拍平到顶层命名空间后,
    # 规则引擎/映射引擎即可用 field_key 与标准字段同等引用。
```

- [ ] **Step 4: 运行测试,确认通过 + 全量回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全量 PASS(142 passed:原 138 + T4 的 2 + T5 的 2)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/mapping_service.py app/tools/bank_journal/schemas/standard.py tests/unit/test_mapping_service.py
git add app/tools/bank_journal/services/mapping_service.py app/tools/bank_journal/schemas/standard.py tests/unit/test_mapping_service.py
git commit -m "refactor(bank-journal): mapping_service 改用 domain 上下文,扩展字段可用(#2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 自定义字段 key 与标准字段冲突校验(收口 #2)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/custom_field_service.py`(创建时校验 `field_key` 不与标准字段冲突)
- Test: `backend/tests/integration/test_custom_fields.py`(新增 422 断言)

**Interfaces:**
- Consumes:`StandardBankTransaction.model_fields`(标准字段名集合)
- Produces:创建自定义字段时 `field_key` ∈ 标准字段名 → 抛 `ValueError`/422

- [ ] **Step 1: 写失败测试**

先读 `tests/integration/test_custom_fields.py` 现有的创建用法(端点路径、payload 形状),仿照新增:

```python
# 追加到 backend/tests/integration/test_custom_fields.py
def test_custom_field_key_colliding_with_standard_rejected(client):
    # field_key 与标准字段 "summary" 冲突 → 422,避免拍平后互相覆盖
    resp = client.post(
        "/api/tools/bank-journal/custom-fields",
        json={"company_id": "company-1", "field_key": "summary",
              "label": "摘要", "data_type": "text"},
    )
    assert resp.status_code == 422
```

(若现有创建测试的 payload 字段名不同,以现有测试为准对齐。)

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_custom_fields.py -k colliding -v`
Expected: FAIL(当前无校验,返回 201)

- [ ] **Step 3: 实现**——在 `custom_field_service` 创建函数入口加校验

```python
# 在 custom_field_service.py 顶部
from app.tools.bank_journal.schemas.standard import StandardBankTransaction

_STANDARD_FIELD_KEYS = set(StandardBankTransaction.model_fields) - {"extra_fields", "raw_row"}

# 在创建自定义字段的函数体最前(校验 field_key 之后),加:
if field_key in _STANDARD_FIELD_KEYS:
    raise ValueError(f"field_key 与标准字段冲突,请改名: {field_key}")
```

(具体把 `raise ValueError` 接入现有的 422 转换路径——参照该文件里既有的校验如何返回 422;若现有校验直接 `raise HTTPException(422)`,则照此风格。)

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest tests/integration/test_custom_fields.py -q`
Expected: PASS(含新断言)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/custom_field_service.py
git add app/tools/bank_journal/services/custom_field_service.py tests/integration/test_custom_fields.py
git commit -m "feat(bank-journal): 自定义字段 key 禁止与标准字段冲突(#2 收口)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: CSV 编码探测,支持 GBK/GB18030(治本 #5)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/parser_service.py:453-459`(`_read_rows` 的 CSV 分支)
- Test: `backend/tests/unit/test_parser_service.py`

**Interfaces:**
- Produces:`_read_rows` 对 CSV 先试 `utf-8-sig`,失败回退 `gb18030`(GBK/GB2312 超集);仍失败抛 `ValueError`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/unit/test_parser_service.py
import csv

from app.tools.bank_journal.services.parser_service import _read_rows


def test_read_rows_decodes_gbk_csv(tmp_path):
    path = tmp_path / "gbk.csv"
    with path.open("w", encoding="gbk", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["日期", "摘要", "金额"])
        writer.writerow(["2026-01-01", "工资", "100"])
    rows = _read_rows(path, "csv", "")
    assert rows[0] == ["日期", "摘要", "金额"]
    assert rows[1][1] == "工资"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_parser_service.py -k gbk -v`
Expected: FAIL(`UnicodeDecodeError`)

- [ ] **Step 3: 实现**——替换 `_read_rows` 的 CSV 分支(453–459 行区域)

```python
    if normalized_type == "csv":
        text = _read_csv_text(file_path)
        return [[_clean_cell(cell) for cell in row] for row in csv.reader(text.splitlines())]
```

并在模块内(`_read_rows` 上方或 `_clean_cell` 附近)新增:

```python
def _read_csv_text(file_path: Path) -> str:
    """按优先级尝试解码:UTF-8(含 BOM)→ GB18030(GBK/GB2312 超集)。"""
    raw = file_path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode CSV: tried utf-8 and gb18030")
```

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest tests/unit/test_parser_service.py -q`
Expected: PASS(含新断言;原 CSV 测试仍绿)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/parser_service.py tests/unit/test_parser_service.py
git add app/tools/bank_journal/services/parser_service.py tests/unit/test_parser_service.py
git commit -m "feat(bank-journal): CSV 编码探测支持 GBK/GB18030(#5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 金额清洗——货币符号/全角/会计括号负数/DR-CR(治本 #6)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/parser_service.py:651-668`(`_decimal_or_none`)
- Test: `backend/tests/unit/test_parser_service.py`

**Interfaces:**
- Produces:`_decimal_or_none` 能解析 `"¥1,234.50"`、`"１，２００"`(全角)、`"(1,000.00)"`→ `-1000`、`"500 DR"`→ `-500`、`"500 CR"`→ `500`;无法解析仍抛 `ValueError`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/unit/test_parser_service.py
from decimal import Decimal

from app.tools.bank_journal.services.parser_service import _decimal_or_none


def test_decimal_cleaning_variants():
    assert _decimal_or_none("¥1,234.50") == Decimal("1234.50")
    assert _decimal_or_none("（1,000.00）") == Decimal("-1000.00")  # 全角括号负数
    assert _decimal_or_none("(1000)") == Decimal("-1000")
    assert _decimal_or_none("500 DR") == Decimal("-500")
    assert _decimal_or_none("500 CR") == Decimal("500")
    assert _decimal_or_none("１２３") == Decimal("123")  # 全角数字
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_parser_service.py -k decimal_cleaning -v`
Expected: FAIL(`Invalid amount`)

- [ ] **Step 3: 实现**——替换 `_decimal_or_none`(651–668 行)

```python
def _decimal_or_none(value: CellValue) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    candidate = _clean_cell(value)
    if not candidate:
        return None

    # 全角 → 半角(数字、逗号、句点、括号、空格)
    candidate = candidate.translate(_FULLWIDTH_MAP)
    negative = False
    # 会计括号负数:(1,000) / （1,000）
    if candidate.startswith("(") and candidate.endswith(")"):
        negative = True
        candidate = candidate[1:-1]
    # 方向后缀 DR/CR
    upper = candidate.upper()
    if upper.endswith("DR"):
        negative = True
        candidate = candidate[:-2]
    elif upper.endswith("CR"):
        candidate = candidate[:-2]
    # 去货币符号、千分位、空白
    for token in ("¥", "￥", "$", "CNY", "RMB", ",", " "):
        candidate = candidate.replace(token, "")
    if not candidate:
        return None

    try:
        result = Decimal(candidate)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value}") from exc
    return -result if negative else result
```

并在模块常量区(如 `DIRECTION_KEYWORDS_*` 附近)新增全角映射:

```python
_FULLWIDTH_MAP = str.maketrans(
    "０１２３４５６７８９．，（）　",
    "0123456789.,()  ",
)
```

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest tests/unit/test_parser_service.py -q`
Expected: PASS(含新断言;原金额测试仍绿)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/parser_service.py tests/unit/test_parser_service.py
git add app/tools/bank_journal/services/parser_service.py tests/unit/test_parser_service.py
git commit -m "feat(bank-journal): 金额清洗支持货币符号/全角/括号负数/DR-CR(#6)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 金额解析改用 SignedAmount + 方向矛盾告警(治本 #4 落到解析)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/parser_service.py`(`_parse_amounts` 及四个 `_parse_*` 改为返回 `SignedAmount`;`_try_parse_row` 适配 + 非致命告警)
- Modify: `backend/app/tools/bank_journal/services/parser_service.py`(`ParsedBankRow` 允许成功行携带 `warnings`)
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(把行级 warnings 并入预览行异常码)
- Test: `backend/tests/unit/test_parser_service.py`

**Interfaces:**
- Consumes:`SignedAmount`(T1)
- Produces:
  - `ParsedBankRow` 新增 `warnings: list[ExceptionCode] = field(default_factory=list)`(成功行的非致命标记)
  - `_parse_amounts(...) -> SignedAmount`(四个 `_parse_*` 同步改为返回 `SignedAmount`)
  - 负数翻转方向时,`_try_parse_row` 给成功行追加 `ExceptionCode.AMOUNT_DIRECTION_MISMATCH` 到 `warnings`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/unit/test_parser_service.py
from app.tools.bank_journal.domain.amounts import SignedAmount
from app.tools.bank_journal.enums import AmountMode, TransactionDirection
from app.tools.bank_journal.services.parser_service import _parse_amounts


def test_parse_amounts_returns_signed_amount():
    sa = _parse_amounts(
        {"income": "100", "expense": ""},
        AmountMode.INCOME_EXPENSE_COLUMNS,
        {"income": "income", "expense": "expense"},
    )
    assert isinstance(sa, SignedAmount)
    assert sa.direction == TransactionDirection.CREDIT
    assert sa.net_amount == Decimal("100")


def test_parse_amounts_negative_income_flags_anomaly():
    sa = _parse_amounts(
        {"income": "-50", "expense": ""},
        AmountMode.INCOME_EXPENSE_COLUMNS,
        {"income": "income", "expense": "expense"},
    )
    assert sa.direction == TransactionDirection.DEBIT
    assert sa.net_amount == Decimal("-50")
    assert sa.sign_anomaly is True
```

> 注:本任务把 `_parse_amounts` 的返回从四元组改为 `SignedAmount`。运行全量前需把 `test_parser_service.py` 中**直接断言四元组**的旧用例改写为断言 `SignedAmount` 属性。改写模式示例:
> 旧 `direction, debit, credit, net = _parse_amounts(...)` → 新 `sa = _parse_amounts(...)`,断言 `sa.direction / sa.debit_amount / sa.credit_amount / sa.net_amount`。

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_parser_service.py -k parse_amounts -v`
Expected: FAIL(当前返回 tuple,无 `.direction` 属性 / 无 SignedAmount)

- [ ] **Step 3: 实现**

(a) `parser_service.py` 顶部 import 增加:
```python
from app.tools.bank_journal.domain.amounts import AmountError, SignedAmount
```

(b) 四个金额解析函数改为返回 `SignedAmount`(去掉手工拼方向/符号):
```python
def _parse_amounts(
    normalized_row: dict[str, CellValue],
    amount_mode: AmountMode,
    amount_config: dict[str, str],
) -> SignedAmount:
    if amount_mode == AmountMode.INCOME_EXPENSE_COLUMNS:
        return SignedAmount.from_income_expense(
            _decimal_or_none(normalized_row.get(amount_config["income"])),
            _decimal_or_none(normalized_row.get(amount_config["expense"])),
        )
    if amount_mode == AmountMode.DEBIT_CREDIT_COLUMNS:
        return SignedAmount.from_debit_credit(
            _decimal_or_none(normalized_row.get(amount_config["debit"])),
            _decimal_or_none(normalized_row.get(amount_config["credit"])),
        )
    if amount_mode == AmountMode.SINGLE_AMOUNT_WITH_DIRECTION:
        amount = _decimal_or_none(normalized_row.get(amount_config["amount"]))
        if amount is None:
            raise AmountError("Unable to determine transaction amount")
        direction_raw = _clean_cell(normalized_row.get(amount_config["direction"]))
        if not direction_raw:
            raise AmountError("Missing direction for single amount mode")
        direction = _direction_from_keyword(direction_raw)
        if direction is None:
            raise AmountError(f"Unknown direction value: {direction_raw}")
        return SignedAmount.from_amount_with_direction(amount, direction)
    if amount_mode == AmountMode.SIGNED_AMOUNT:
        amount = _decimal_or_none(normalized_row.get(amount_config["amount"]))
        if amount is None:
            raise AmountError("Unable to determine transaction amount")
        return SignedAmount.from_signed(amount)
    raise ValueError(f"Unsupported amount mode: {amount_mode}")
```
删除现已无用的 `_parse_income_expense_columns`/`_parse_debit_credit_columns`/`_parse_single_amount_with_direction`/`_parse_signed_amount`。注意 `AmountError` 继承 `ValueError`,`_try_parse_row` 的 `except ValueError` 仍捕获 → 致命金额错误照旧产出 PARSE_FAILED。

(c) `ParsedBankRow` 增加 `warnings` 字段(在 `parse_errors` 行下方):
```python
    warnings: list[ExceptionCode] = field(default_factory=list)
```

(d) `_try_parse_row` 金额段(200–213 行)改为:
```python
    try:
        amount = _parse_amounts(normalized_row, config.amount_mode, config.amount_config)
    except ValueError as exc:
        message = str(exc)
        base.parse_errors.append(ExceptionCode.INVALID_AMOUNT)
        if "direction" in message.lower():
            base.parse_errors[-1] = ExceptionCode.UNKNOWN_DIRECTION
        base.error_message = message
        return base

    if amount.sign_anomaly:
        base.warnings.append(ExceptionCode.AMOUNT_DIRECTION_MISMATCH)
```
并把构造 `StandardBankTransaction` 的金额三参(241–243 行)改为:
```python
        direction=amount.direction,
        debit_amount=amount.debit_amount,
        credit_amount=amount.credit_amount,
        net_amount=amount.net_amount,
```

(e) `conversion_service.run_conversion` 成功行分支:把 `parsed.warnings` 并入预览行异常码。在第 208 行 `build_preview_row(...)` 得到 `preview` 后,合并:
```python
            for code in parsed.warnings:
                if code not in preview.exception_codes:
                    preview.exception_codes.append(code)
```
(若 `preview.exception_codes` 也用于落库 `exception_codes_json`,确认两处都写入。)

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全量 PASS(改写后的 parser 旧断言 + 新断言)

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/parser_service.py app/tools/bank_journal/services/conversion_service.py tests/unit/test_parser_service.py
git add app/tools/bank_journal/services/parser_service.py app/tools/bank_journal/services/conversion_service.py tests/unit/test_parser_service.py
git commit -m "refactor(bank-journal): 金额解析改用 SignedAmount,负数翻向并告警(#4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 扩展 date 字段以 date 对象落库(治本 #7)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py:591-596`(`_build_bank_transaction` 写 slot 时按类型转换)
- Test: `backend/tests/unit/test_conversion_service.py`

**Interfaces:**
- Produces:`_build_bank_transaction` 对 `data_type == "date"` 的扩展字段,把 ISO 串转 `date` 后再赋值给 Date 列

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/unit/test_conversion_service.py
from datetime import date
from decimal import Decimal

from app.tools.bank_journal.services.conversion_service import _build_bank_transaction
from app.tools.bank_journal.services.parser_service import CustomFieldDef
from app.tools.bank_journal.enums import TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def test_extended_date_field_stored_as_date():
    txn = StandardBankTransaction(
        transaction_date="2026-01-01",
        bank_account_id="acc-1",
        direction=TransactionDirection.CREDIT,
        net_amount=Decimal("1"),
        extra_fields={"due_date": "2026-03-15"},
        source_file_id="f-1", source_sheet_name="S", source_row_index=2, raw_row={},
    )
    slot_map = {"due_date": CustomFieldDef(
        field_key="due_date", slot_key="ext_date_1", data_type="date", header_keywords=[])}
    bt = _build_bank_transaction("run-1", txn, slot_map)
    assert bt.ext_date_1 == date(2026, 3, 15)  # 是 date 对象而非字符串
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_conversion_service.py -k extended_date -v`
Expected: FAIL(`bt.ext_date_1` 是字符串 `"2026-03-15"`,断言不等)

- [ ] **Step 3: 实现**——替换 591–596 行的 slot 写入块

```python
    # 把 extra_fields 按 field_key → slot_key 反查,按类型转换后写入对应预分配列。
    if slot_map and txn.extra_fields:
        for field_key, value in txn.extra_fields.items():
            cf = slot_map.get(field_key)
            if cf is None or value is None:
                continue
            if cf.data_type == "date" and isinstance(value, str):
                value = date.fromisoformat(value)
            kwargs[cf.slot_key] = value
```

(`date` 已在 `conversion_service.py` 顶部 import;若没有则补 `from datetime import date`。)

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全量 PASS

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/conversion_service.py tests/unit/test_conversion_service.py
git add app/tools/bank_journal/services/conversion_service.py tests/unit/test_conversion_service.py
git commit -m "fix(bank-journal): 扩展 date 字段以 date 对象落库,兼容 PostgreSQL(#7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 转换逐行错误隔离(治本 #3)

**Files:**
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py:204-214`(成功行分支包裹 try/except)
- Test: `backend/tests/integration/test_conversion_api.py` 或 `tests/unit/test_conversion_service.py`

**Interfaces:**
- Produces:单行在 `_build_bank_transaction`/`build_preview_row` 抛错时,产出 `PARSE_FAILED` 预览行(带错误信息)并 `continue`,**不中断整批**

- [ ] **Step 1: 写失败测试**(集成层最直观:一个映射引用不存在字段,只应让命中的行失败,其余成功)

先读 `tests/integration/test_conversion_api.py` 了解构造 run 的现有夹具,仿造一个"映射来源为不存在字段"的批次,断言:响应 200、存在 PARSE_FAILED 行、其余行正常。骨架:

```python
# backend/tests/integration/test_conversion_api.py 追加
def test_bad_mapping_isolated_per_row(client, seeded_run_payload):
    payload = seeded_run_payload  # 含 2 行有效流水的既有夹具
    payload["mappings"] = [{"target": "科目", "type": "field", "source": "不存在字段"}]
    resp = client.post("/api/tools/bank-journal/conversion-runs", json=payload)
    assert resp.status_code == 200  # 整批不再 500
    rows = resp.json()["preview_rows"]
    assert all(r["status"] == "parse_failed" for r in rows)  # 逐行降级而非整批崩
```

(若现有夹具命名不同,以该文件实际夹具为准;关键断言是"200 而非 500 + 行级降级"。)

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/integration/test_conversion_api.py -k bad_mapping_isolated -v`
Expected: FAIL(当前 `apply_mappings` 抛 ValueError 未捕获 → 500)

- [ ] **Step 3: 实现**——把 204–214 行成功行分支改为带隔离:

```python
            transaction = parsed.transaction
            try:
                bank_tx = _build_bank_transaction(
                    run.id, transaction, _slot_map_for(custom_defs)
                )
                db.add(bank_tx)
                preview = build_preview_row(
                    transaction,
                    payload.mappings,
                    payload.rules,
                    payload.required_columns,
                    row_index,
                )
                for code in parsed.warnings:
                    if code not in preview.exception_codes:
                        preview.exception_codes.append(code)
            except Exception as exc:  # noqa: BLE001  单行隔离:任何处理错误降级为失败行,不中断整批
                preview_id = str(uuid4())
                db.add(
                    JournalPreviewRow(
                        id=preview_id,
                        conversion_run_id=run.id,
                        bank_transaction_id=None,
                        row_index=row_index,
                        output_values_json={"_processing_error": str(exc)},
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes_json=[ExceptionCode.INVALID_AMOUNT.value],
                        matched_rule_versions_json=[],
                        rule_trace_json=[],
                    )
                )
                preview_rows.append(
                    JournalPreviewRowData(
                        id=preview_id,
                        row_index=row_index,
                        output_values={"_processing_error": str(exc)},
                        status=PreviewStatus.PARSE_FAILED,
                        exception_codes=[ExceptionCode.INVALID_AMOUNT],
                        matched_rule_version_ids=[],
                        rule_trace=[],
                    )
                )
                parse_failed_count += 1
                row_index += 1
                continue
```
其后保留原有"把 `preview` 落库 + append 到 `preview_rows`"的代码块不变。

> 说明:这是把 #3 的错误隔离落到现有 `run_conversion` 循环(最小且安全)。spec 的"纯阶段 `run_pipeline()` 抽取"作为后续可选整合,不在本计划——功能性目标(单行错误不炸整批)已由本任务达成。

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全量 PASS

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/services/conversion_service.py tests/integration/test_conversion_api.py
git add app/tools/bank_journal/services/conversion_service.py tests/integration/test_conversion_api.py
git commit -m "fix(bank-journal): 转换逐行错误隔离,坏行降级不中断整批(#3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: row_hash 计算 + 批内/历史去重(实装 gap P1-3 之一)

**Files:**
- Create: `backend/app/tools/bank_journal/domain/dedup.py`(纯函数:算 hash + 标注重复)
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(注入历史查询 + 给 `bank_tx` 写 `row_hash` + 给重复行加异常码)
- Test: `backend/tests/unit/test_domain_dedup.py`

**Interfaces:**
- Produces:
  - `def row_hash(txn: StandardBankTransaction, key_fields: list[str]) -> str` —— 对配置的关键字段做稳定 sha256
  - `def mark_duplicates(hashes: list[str], history: set[str]) -> list[ExceptionCode | None]` —— 逐行返回 `DUPLICATE_IN_BATCH`/`DUPLICATE_HISTORY`/`None`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_domain_dedup.py
from decimal import Decimal

from app.tools.bank_journal.domain.dedup import mark_duplicates, row_hash
from app.tools.bank_journal.enums import ExceptionCode, TransactionDirection
from app.tools.bank_journal.schemas.standard import StandardBankTransaction


def _txn(net):
    return StandardBankTransaction(
        transaction_date="2026-01-01", bank_account_id="acc-1",
        direction=TransactionDirection.CREDIT, net_amount=Decimal(net),
        summary="货款", source_file_id="f", source_sheet_name="S",
        source_row_index=2, raw_row={},
    )


def test_row_hash_stable_and_distinct():
    keys = ["transaction_date", "net_amount", "summary"]
    assert row_hash(_txn("100"), keys) == row_hash(_txn("100"), keys)
    assert row_hash(_txn("100"), keys) != row_hash(_txn("200"), keys)


def test_mark_duplicates_in_batch_and_history():
    hashes = ["a", "a", "b"]
    history = {"b"}
    result = mark_duplicates(hashes, history)
    assert result[0] is None
    assert result[1] == ExceptionCode.DUPLICATE_IN_BATCH
    assert result[2] == ExceptionCode.DUPLICATE_HISTORY
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_dedup.py -v`
Expected: FAIL(`ModuleNotFoundError ... domain.dedup`)

- [ ] **Step 3: 实现**

```python
# backend/app/tools/bank_journal/domain/dedup.py
from __future__ import annotations

import hashlib

from app.tools.bank_journal.domain.fields import EvaluationContext
from app.tools.bank_journal.enums import ExceptionCode
from app.tools.bank_journal.schemas.standard import StandardBankTransaction

_DEFAULT_KEY_FIELDS = ["transaction_date", "net_amount", "summary", "counterparty_account_no"]


def row_hash(txn: StandardBankTransaction, key_fields: list[str] | None = None) -> str:
    ctx = EvaluationContext.from_transaction(txn)
    fields = key_fields or _DEFAULT_KEY_FIELDS
    parts = [f"{k}={ctx.get(k)!r}" for k in fields]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def mark_duplicates(
    hashes: list[str], history: set[str]
) -> list[ExceptionCode | None]:
    seen: set[str] = set()
    result: list[ExceptionCode | None] = []
    for h in hashes:
        if h in seen:
            result.append(ExceptionCode.DUPLICATE_IN_BATCH)
        elif h in history:
            result.append(ExceptionCode.DUPLICATE_HISTORY)
        else:
            result.append(None)
        seen.add(h)
    return result
```

(b) `conversion_service`:在落库每个 `bank_tx` 时写 `row_hash`,并在批次处理后对全部成功行调用 `mark_duplicates`(history 来自一次性查询 `BankTransaction.row_hash`,按 `company_id` 关联 run),把非 None 的码并入对应预览行的 `exception_codes_json`。实现要点:
- `bank_tx.row_hash = row_hash(transaction, config_key_fields)`(`config_key_fields` 取自 `unique_key_config`,无则用默认)。
- 历史集合:`history = {h for (h,) in db.query(BankTransaction.row_hash).join(ConversionRun).filter(ConversionRun.company_id == payload.company_id, BankTransaction.row_hash.isnot(None))}`(在本批写入前查)。
- 批末统一标注:把本批 hash 列表 + history 传入 `mark_duplicates`,按行 append 异常码并更新已落库的 `JournalPreviewRow.exception_codes_json`。

> 该步是 service 编排,代码随现有结构组织;核心纯逻辑(hash + 标注)已在 `domain/dedup.py` 且有单测覆盖。集成断言放入 `tests/integration/test_conversion_api.py`:上传含重复行的批次,断言重复行带 `DUPLICATE_IN_BATCH`。

- [ ] **Step 4: 运行测试,确认通过 + 回归**

Run: `cd backend && .venv/bin/pytest -q`
Expected: 全量 PASS

- [ ] **Step 5: 提交**

```bash
cd backend && ruff check app/tools/bank_journal/domain/dedup.py app/tools/bank_journal/services/conversion_service.py tests/unit/test_domain_dedup.py
git add app/tools/bank_journal/domain/dedup.py app/tools/bank_journal/services/conversion_service.py tests/unit/test_domain_dedup.py tests/integration/test_conversion_api.py
git commit -m "feat(bank-journal): row_hash 计算与批内/历史去重(gap P1-3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: 余额连续性校验(实装 gap P1-3 之二)

**Files:**
- Create: `backend/app/tools/bank_journal/domain/balance.py`
- Modify: `backend/app/tools/bank_journal/services/conversion_service.py`(按文件行序调用,给跳变行加异常码)
- Test: `backend/tests/unit/test_domain_balance.py`

**Interfaces:**
- Produces:`def check_balance_continuity(rows: list[tuple[Decimal|None, Decimal]]) -> list[bool]` —— 入参为逐行 `(balance, net_amount)`(按时间/行序),返回逐行"是否跳变"(`True`=不连续)。首行或缺 balance → `False`(不判)。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_domain_balance.py
from decimal import Decimal

from app.tools.bank_journal.domain.balance import check_balance_continuity


def test_continuous_balance_no_flag():
    rows = [
        (Decimal("100"), Decimal("100")),  # 首行不判
        (Decimal("150"), Decimal("50")),   # 100 + 50 = 150 ✓
        (Decimal("120"), Decimal("-30")),  # 150 - 30 = 120 ✓
    ]
    assert check_balance_continuity(rows) == [False, False, False]


def test_discontinuity_flagged():
    rows = [
        (Decimal("100"), Decimal("100")),
        (Decimal("999"), Decimal("50")),   # 期望 150,实际 999 → 跳变
    ]
    assert check_balance_continuity(rows) == [False, True]


def test_missing_balance_not_flagged():
    rows = [(Decimal("100"), Decimal("100")), (None, Decimal("50"))]
    assert check_balance_continuity(rows) == [False, False]
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd backend && .venv/bin/pytest tests/unit/test_domain_balance.py -v`
Expected: FAIL(`ModuleNotFoundError ... domain.balance`)

- [ ] **Step 3: 实现**

```python
# backend/app/tools/bank_journal/domain/balance.py
from __future__ import annotations

from decimal import Decimal


def check_balance_continuity(rows: list[tuple[Decimal | None, Decimal]]) -> list[bool]:
    """逐行判断余额是否连续。rows 按行序给出 (balance, net_amount)。

    规则:本行 balance 应 ≈ 上一行 balance + 本行 net_amount。
    首行、本行或上一行缺 balance 时不判(False)。
    """
    flags: list[bool] = []
    prev_balance: Decimal | None = None
    for balance, net in rows:
        if prev_balance is None or balance is None:
            flags.append(False)
        else:
            flags.append(balance != prev_balance + net)
        if balance is not None:
            prev_balance = balance
    return flags
```

(b) `conversion_service`:对每个 source_file 的成功行(按 `source_row_index` 升序)收集 `(balance, net_amount)`,调 `check_balance_continuity`,对 `True` 的行把 `ExceptionCode.BALANCE_DISCONTINUITY` 并入其 `exception_codes_json`。集成断言加入 `tests/integration/test_conversion_api.py`(构造一个余额跳变的流水,断言该行带 `BALANCE_DISCONTINUITY`)。

- [ ] **Step 4: 运行测试,确认通过 + 全量 + lint**

Run: `cd backend && .venv/bin/pytest -q && ruff check .`
Expected: 全量 PASS、ruff 干净

- [ ] **Step 5: 提交**

```bash
git add app/tools/bank_journal/domain/balance.py app/tools/bank_journal/services/conversion_service.py tests/unit/test_domain_balance.py tests/integration/test_conversion_api.py
git commit -m "feat(bank-journal): 余额连续性校验(gap P1-3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 收尾:全量验证 + 前端 e2e 回归

- [ ] 后端:`cd backend && .venv/bin/pytest -q`(全绿)、`ruff check .`(干净)。
- [ ] 前端:`cd frontend && npm run build && npm run e2e`(7/7 绿——确认重构未破坏 API 契约形状)。
- [ ] 对照 spec §7 验收清单逐条确认。

## 自检:spec 覆盖映射

| spec 验收项 | 任务 |
|------|------|
| `all/any/not` + `any` 正确 + 空/未知处理(#1) | T3, T4 |
| 自定义字段可作条件与映射来源 + 注释更正(#2) | T2, T4, T5, T6 |
| 单行错误不中断整批(#3) | T11 |
| 负数翻向 / `AMOUNT_DIRECTION_MISMATCH`(#4) | T1, T9 |
| GBK/GB18030(#5) | T7 |
| 货币符号/全角/括号负数/DR-CR(#6) | T8 |
| 扩展 date 字段以 date 落库(#7) | T10 |
| `row_hash` + 批内/历史去重 + 余额连续性(gap P1-3) | T12, T13 |
| `conditional` 映射可用 | T5(路由经 domain,已存在) |
| 138 后端 + 7 e2e 全绿 + 新增测试 | 各任务 Step 4 + 收尾 |
| 历史批次只读不受影响 | 全程只改新转换路径;收尾 e2e 回归 |

> 范围外(后续工作流):typed Rule/Mapping 输入契约 + 422(W2);分页/索引(W2);鉴权/RBAC/租户/加密/FK pragma(W3);迁移契约/PG 实测/异步(W4);前端动态列/编辑选项/状态同步/代码分割(W5)。
