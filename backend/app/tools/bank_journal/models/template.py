from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import IdMixin, TimestampMixin


class BankTemplate(Base, IdMixin, TimestampMixin):
    __tablename__ = "bank_templates"

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(255))
    bank_account_id: Mapped[str | None] = mapped_column(ForeignKey("bank_accounts.id"))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )


class BankTemplateVersion(Base, IdMixin):
    __tablename__ = "bank_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "bank_template_id",
            "version_no",
            name="uq_bank_template_versions_version",
        ),
    )

    bank_template_id: Mapped[str] = mapped_column(ForeignKey("bank_templates.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sheet_selector_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    header_row_index: Mapped[int | None] = mapped_column(Integer)
    data_start_row_index: Mapped[int | None] = mapped_column(Integer)
    field_aliases_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    date_formats_json: Mapped[list[str] | None] = mapped_column(JSON)
    amount_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_config_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    unique_key_config_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    sample_file_id: Mapped[str | None] = mapped_column(ForeignKey("source_files.id"))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CompanyJournalTemplate(Base, IdMixin, TimestampMixin):
    __tablename__ = "company_journal_templates"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )


class CompanyJournalTemplateVersion(Base, IdMixin):
    __tablename__ = "company_journal_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "company_journal_template_id",
            "version_no",
            name="uq_company_journal_template_versions_version",
        ),
    )

    company_journal_template_id: Mapped[str] = mapped_column(
        ForeignKey("company_journal_templates.id"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    header_row_index: Mapped[int | None] = mapped_column(Integer)
    data_start_row_index: Mapped[int | None] = mapped_column(Integer)
    columns_json: Mapped[list[dict[str, object]] | None] = mapped_column(JSON)
    required_columns_json: Mapped[list[str] | None] = mapped_column(JSON)
    format_rules_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    sample_file_id: Mapped[str | None] = mapped_column(ForeignKey("source_files.id"))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
