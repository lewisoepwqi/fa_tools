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
        """从交易对象创建上下文。

        若自定义字段 key 与标准字段同名,自定义值覆盖标准值
        (此冲突已由 custom_field_service 在创建期拦截)。
        """
        data = txn.model_dump()
        extra = data.pop("extra_fields", None) or {}
        data.update(extra)  # 关键:扩展字段提到顶层,与标准字段同权
        return cls(data)
