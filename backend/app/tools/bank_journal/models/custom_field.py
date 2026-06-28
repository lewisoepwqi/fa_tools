"""公司级自定义扩展字段定义。

每个公司可维护自己的扩展字段（如「成本中心」「项目代号」），把业务名绑定到
``bank_transactions`` 表上一个中性的预分配强类型槽位（``ext_text_1`` 等）。

- ``field_key``：进入标准字段空间的 key，规则/映射引擎通过 ``model_dump()`` 引用它
- ``slot_key``：实际落库的列名（必须是预分配列之一），公司内一个槽位只能绑一个字段
- ``data_type``：text/amount/date，决定槽位类型族与解析方式
- ``header_keywords_json``：中文表头识别关键词，detect 时自动匹配

约束：``(company_id, field_key)`` 与 ``(company_id, slot_key)`` 均唯一。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import IdMixin, TimestampMixin

# 预分配槽位清单（与 BankTransaction 模型的 ext_* 列一一对应）。
# 暴露给路由层做创建校验与剩余配额计算。
TEXT_SLOTS = [f"ext_text_{i}" for i in range(1, 9)]
AMOUNT_SLOTS = [f"ext_amount_{i}" for i in range(1, 5)]
DATE_SLOTS = [f"ext_date_{i}" for i in range(1, 3)]
ALL_SLOTS = TEXT_SLOTS + AMOUNT_SLOTS + DATE_SLOTS

# data_type → 可用槽位列表
SLOTS_BY_TYPE: dict[str, list[str]] = {
    "text": TEXT_SLOTS,
    "amount": AMOUNT_SLOTS,
    "date": DATE_SLOTS,
}


class CustomField(Base, IdMixin, TimestampMixin):
    __tablename__ = "custom_fields"
    __table_args__ = (
        UniqueConstraint("company_id", "field_key", name="uq_custom_fields_company_field_key"),
        UniqueConstraint("company_id", "slot_key", name="uq_custom_fields_company_slot_key"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    # 标准字段空间名（规则/映射引用此 key，进入 model_dump）
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # 面向财务人员的业务名称（如下拉展示）
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 实际落库列（预分配槽位之一）
    slot_key: Mapped[str] = mapped_column(String(32), nullable=False)
    # text / amount / date
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # 中文表头识别关键词数组，detect 时自动匹配
    header_keywords_json: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
