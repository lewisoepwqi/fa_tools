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
