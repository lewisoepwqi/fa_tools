from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import IdMixin, TimestampMixin


class Rule(Base, IdMixin, TimestampMixin):
    __tablename__ = "rules"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str | None] = mapped_column(String(64))
    scope_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )


class RuleVersion(Base, IdMixin):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version_no", name="uq_rule_versions"),)

    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int | None] = mapped_column(Integer)
    conditions_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    actions_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    allow_auto_confirm: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
