from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.tools.bank_journal.domain.fields import EvaluationContext


def evaluate(node: dict[str, Any], ctx: EvaluationContext) -> bool:
    if not isinstance(node, dict):
        raise ValueError(f"Invalid condition node: {node!r}")
    if not node:
        return False  # 无条件 → 不匹配任何行(防止误配的空规则套用全部)
    if "all" in node:
        children = node["all"]
        # 空 all 视为"无真实条件" → 不匹配(而非数学上的 all([])==True)
        return bool(children) and all(evaluate(child, ctx) for child in children)
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
