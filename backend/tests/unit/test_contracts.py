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


def test_mapping_extra_key_ignored_not_rejected():
    """_advanced 透传向后兼容：带 stale extra 键的 fixed 映射应被接受，序列化后 extra 键消失。"""
    # 前端在 type 切换为 fixed 后留了 source 残余字段：不能触发 ValidationError
    result = _mapping_adapter.validate_python(
        {"type": "fixed", "target": "科目", "value": "x", "source": "stale"}
    )
    # extra 键已被 ignore，序列化输出不含 source
    dumped = result.model_dump()
    assert dumped["target"] == "科目"
    assert dumped["value"] == "x"
    assert "source" not in dumped

    # 未知 type 依然拒绝（discriminator 保护完好）
    with pytest.raises(ValidationError):
        _mapping_adapter.validate_python({"type": "bogus", "target": "x", "extra_key": "v"})

    # field 缺 source 依然拒绝（必填字段保护完好）
    with pytest.raises(ValidationError):
        _mapping_adapter.validate_python({"type": "field", "target": "x", "extra_key": "v"})
