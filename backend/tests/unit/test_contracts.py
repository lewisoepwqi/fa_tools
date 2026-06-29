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
    _mapping_adapter.validate_python(
        {"type": "concat", "target": "摘要", "sources": ["a", "b"], "separator": "-"}
    )
    _mapping_adapter.validate_python({"type": "fixed", "target": "币种", "value": "CNY"})
    with pytest.raises(ValidationError):
        _mapping_adapter.validate_python({"type": "bogus", "target": "x"})  # 未知 type
    with pytest.raises(ValidationError):
        _mapping_adapter.validate_python({"type": "field", "target": "x"})  # field 缺 source
