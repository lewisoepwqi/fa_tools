from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedString
from app.db.base import Base
from app.models.common import IdMixin, TimestampMixin


class ConversionRun(Base, IdMixin):
    __tablename__ = "conversion_runs"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    bank_account_id: Mapped[str | None] = mapped_column(ForeignKey("bank_accounts.id"))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    bank_template_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("bank_template_versions.id")
    )
    company_journal_template_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_journal_template_versions.id")
    )
    mapping_profile_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("mapping_profile_versions.id")
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConversionRunFile(Base, IdMixin):
    __tablename__ = "conversion_run_files"

    conversion_run_id: Mapped[str] = mapped_column(
        ForeignKey("conversion_runs.id"), nullable=False, index=True
    )
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_files.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    row_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ConversionRunRuleVersion(Base, IdMixin):
    __tablename__ = "conversion_run_rule_versions"

    conversion_run_id: Mapped[str] = mapped_column(
        ForeignKey("conversion_runs.id"), nullable=False, index=True
    )
    rule_version_id: Mapped[str] = mapped_column(ForeignKey("rule_versions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class BankTransaction(Base, IdMixin):
    __tablename__ = "bank_transactions"

    conversion_run_id: Mapped[str] = mapped_column(
        ForeignKey("conversion_runs.id"), nullable=False, index=True
    )
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_files.id"), nullable=False)
    source_sheet_name: Mapped[str | None] = mapped_column(String(255))
    source_row_index: Mapped[int | None] = mapped_column(Integer)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date | None] = mapped_column(Date)
    bank_account_id: Mapped[str | None] = mapped_column(ForeignKey("bank_accounts.id"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(32))
    debit_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    credit_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    counterparty_name: Mapped[str | None] = mapped_column(String(255))
    counterparty_account_no_encrypted: Mapped[str | None] = mapped_column(EncryptedString(512))
    counterparty_bank_name: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(String(255))
    purpose: Mapped[str | None] = mapped_column(String(255))
    transaction_type: Mapped[str | None] = mapped_column(String(255))
    bank_transaction_id: Mapped[str | None] = mapped_column(String(128))
    receipt_no: Mapped[str | None] = mapped_column(String(128))
    raw_row_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    # 公司级自定义扩展字段的中性预分配强类型列（见 CustomField）。
    # 用户在 UI 把业务字段（如「成本中心」）绑定到某个空闲槽位；运行时零 DDL。
    # 文本槽 8 个、金额槽 4 个、日期槽 2 个，超出需重新迁移扩容。
    ext_text_1: Mapped[str | None] = mapped_column(String(255))
    ext_text_2: Mapped[str | None] = mapped_column(String(255))
    ext_text_3: Mapped[str | None] = mapped_column(String(255))
    ext_text_4: Mapped[str | None] = mapped_column(String(255))
    ext_text_5: Mapped[str | None] = mapped_column(String(255))
    ext_text_6: Mapped[str | None] = mapped_column(String(255))
    ext_text_7: Mapped[str | None] = mapped_column(String(255))
    ext_text_8: Mapped[str | None] = mapped_column(String(255))
    ext_amount_1: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    ext_amount_2: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    ext_amount_3: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    ext_amount_4: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    ext_date_1: Mapped[date | None] = mapped_column(Date)
    ext_date_2: Mapped[date | None] = mapped_column(Date)
    row_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class JournalPreviewRow(Base, IdMixin, TimestampMixin):
    __tablename__ = "journal_preview_rows"

    conversion_run_id: Mapped[str] = mapped_column(
        ForeignKey("conversion_runs.id"), nullable=False, index=True
    )
    bank_transaction_id: Mapped[str | None] = mapped_column(ForeignKey("bank_transactions.id"))
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    output_values_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="needs_confirmation",
        server_default=text("'needs_confirmation'"),
    )
    exception_codes_json: Mapped[list[str] | None] = mapped_column(JSON)
    matched_rule_versions_json: Mapped[list[str] | None] = mapped_column(JSON)
    rule_trace_json: Mapped[dict[str, object] | None] = mapped_column(JSON)


class ManualAdjustment(Base, IdMixin):
    __tablename__ = "manual_adjustments"

    journal_preview_row_id: Mapped[str] = mapped_column(
        ForeignKey("journal_preview_rows.id"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text())
    new_value: Mapped[str | None] = mapped_column(Text())
    reason: Mapped[str | None] = mapped_column(Text())
    adjusted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Confirmation(Base, IdMixin):
    __tablename__ = "confirmations"

    journal_preview_row_id: Mapped[str] = mapped_column(
        ForeignKey("journal_preview_rows.id"),
        nullable=False,
    )
    confirmation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text())


class Export(Base, IdMixin):
    __tablename__ = "exports"

    conversion_run_id: Mapped[str] = mapped_column(ForeignKey("conversion_runs.id"), nullable=False)
    exported_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    report_storage_key: Mapped[str | None] = mapped_column(String(512))
    row_count: Mapped[int | None] = mapped_column(Integer)
    only_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
