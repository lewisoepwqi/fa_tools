"""公司级内置标准字段覆盖。

内置标准字段（transaction_date 等 18 个）的 key 是后端解析引擎/DB 列的硬契约，不可改。
但其展示名称(label)、识别关键词(header keywords)、规则操作符类型(type) 可按公司覆盖。

- ``field_key``：被覆盖的内置字段 key（必须在 BUILTIN_FIELD_KEYS 内，不可改 key 本身）
- ``label_override``：None 表示用内置默认 label
- ``header_keywords_override``：None 表示用内置默认关键词；用户加的关键词与内置默认 union
- ``type_override``：None 表示用内置默认 type；仅影响规则操作符过滤，不影响实际解析

约束：``(company_id, field_key)`` 唯一。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import IdMixin


class BuiltinFieldOverride(Base, IdMixin):
    __tablename__ = "builtin_field_overrides"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "field_key", name="uq_builtin_overrides_company_field_key"
        ),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    # 被覆盖的内置字段 key（不可改 key 本身）
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label_override: Mapped[str | None] = mapped_column(String(64))
    header_keywords_override: Mapped[list[str] | None] = mapped_column(JSON)
    # 仅影响规则操作符过滤（text/amount/date/enum），不影响实际解析
    type_override: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
