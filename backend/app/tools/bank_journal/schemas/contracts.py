from __future__ import annotations

from typing import Annotated, Any, Literal

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

    all: list[ConditionIn] | None = None
    any: list[ConditionIn] | None = None
    not_: ConditionIn | None = Field(default=None, alias="not")
    field: str | None = None
    op: Operator | None = None
    value: Any = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _exactly_one_form(self) -> ConditionIn:
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


# 处理空 all=[]: all is not None(是 list),branches sum=1 ✓
# 处理 {} : all/any/not_/field 全 None, sum=0 → ValueError ✓

ConditionIn.model_rebuild()


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


_MappingUnion = (
    FieldMapping
    | FixedMapping
    | RuleOutputMapping
    | ConcatMapping
    | ConditionalMapping
    | ManualMapping
)
MappingIn = Annotated[_MappingUnion, Field(discriminator="type")]
