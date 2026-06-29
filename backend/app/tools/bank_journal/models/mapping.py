from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import IdMixin, TimestampMixin


class MappingProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "mapping_profiles"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_template_id: Mapped[str | None] = mapped_column(ForeignKey("bank_templates.id"))
    company_journal_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_journal_templates.id")
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )


class MappingProfileVersion(Base, IdMixin):
    __tablename__ = "mapping_profile_versions"
    __table_args__ = (
        UniqueConstraint("mapping_profile_id", "version_no", name="uq_mapping_profile_versions"),
        Index("ix_mapping_profile_versions_parent_ver", "mapping_profile_id", "version_no"),
    )

    mapping_profile_id: Mapped[str] = mapped_column(
        ForeignKey("mapping_profiles.id"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    bank_template_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("bank_template_versions.id")
    )
    company_journal_template_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_journal_template_versions.id")
    )
    mappings_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
