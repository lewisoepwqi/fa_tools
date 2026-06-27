"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-27 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True, unique=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("bank_name", sa.String(length=255), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_no_encrypted", sa.String(length=512), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'CNY'"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "source_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "bank_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column(
            "bank_account_id",
            sa.String(length=36),
            sa.ForeignKey("bank_accounts.id"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "company_journal_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "bank_template_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "bank_template_id",
            sa.String(length=36),
            sa.ForeignKey("bank_templates.id"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("sheet_selector_json", sa.JSON(), nullable=True),
        sa.Column("header_row_index", sa.Integer(), nullable=True),
        sa.Column("data_start_row_index", sa.Integer(), nullable=True),
        sa.Column("field_aliases_json", sa.JSON(), nullable=True),
        sa.Column("date_formats_json", sa.JSON(), nullable=True),
        sa.Column("amount_mode", sa.String(length=64), nullable=False),
        sa.Column("amount_config_json", sa.JSON(), nullable=True),
        sa.Column("unique_key_config_json", sa.JSON(), nullable=True),
        sa.Column(
            "sample_file_id",
            sa.String(length=36),
            sa.ForeignKey("source_files.id"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "bank_template_id",
            "version_no",
            name="uq_bank_template_versions_version",
        ),
    )
    op.create_table(
        "company_journal_template_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_journal_template_id",
            sa.String(length=36),
            sa.ForeignKey("company_journal_templates.id"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column("header_row_index", sa.Integer(), nullable=True),
        sa.Column("data_start_row_index", sa.Integer(), nullable=True),
        sa.Column("columns_json", sa.JSON(), nullable=True),
        sa.Column("required_columns_json", sa.JSON(), nullable=True),
        sa.Column("format_rules_json", sa.JSON(), nullable=True),
        sa.Column(
            "sample_file_id",
            sa.String(length=36),
            sa.ForeignKey("source_files.id"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "company_journal_template_id",
            "version_no",
            name="uq_company_journal_template_versions_version",
        ),
    )
    op.create_table(
        "mapping_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "bank_template_id",
            sa.String(length=36),
            sa.ForeignKey("bank_templates.id"),
            nullable=True,
        ),
        sa.Column(
            "company_journal_template_id",
            sa.String(length=36),
            sa.ForeignKey("company_journal_templates.id"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "mapping_profile_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "mapping_profile_id",
            sa.String(length=36),
            sa.ForeignKey("mapping_profiles.id"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "bank_template_version_id",
            sa.String(length=36),
            sa.ForeignKey("bank_template_versions.id"),
            nullable=True,
        ),
        sa.Column(
            "company_journal_template_version_id",
            sa.String(length=36),
            sa.ForeignKey("company_journal_template_versions.id"),
            nullable=True,
        ),
        sa.Column("mappings_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("mapping_profile_id", "version_no", name="uq_mapping_profile_versions"),
    )
    op.create_table(
        "rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=64), nullable=True),
        sa.Column("scope_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "rule_id",
            sa.String(length=36),
            sa.ForeignKey("rules.id"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("actions_json", sa.JSON(), nullable=True),
        sa.Column("allow_auto_confirm", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("rule_id", "version_no", name="uq_rule_versions"),
    )
    op.create_table(
        "conversion_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "bank_account_id",
            sa.String(length=36),
            sa.ForeignKey("bank_accounts.id"),
            nullable=True,
        ),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "bank_template_version_id",
            sa.String(length=36),
            sa.ForeignKey("bank_template_versions.id"),
            nullable=True,
        ),
        sa.Column(
            "company_journal_template_version_id",
            sa.String(length=36),
            sa.ForeignKey("company_journal_template_versions.id"),
            nullable=True,
        ),
        sa.Column(
            "mapping_profile_version_id",
            sa.String(length=36),
            sa.ForeignKey("mapping_profile_versions.id"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "conversion_run_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversion_run_id",
            sa.String(length=36),
            sa.ForeignKey("conversion_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.String(length=36),
            sa.ForeignKey("source_files.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "conversion_run_rule_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversion_run_id",
            sa.String(length=36),
            sa.ForeignKey("conversion_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "rule_version_id",
            sa.String(length=36),
            sa.ForeignKey("rule_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversion_run_id",
            sa.String(length=36),
            sa.ForeignKey("conversion_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.String(length=36),
            sa.ForeignKey("source_files.id"),
            nullable=False,
        ),
        sa.Column("source_sheet_name", sa.String(length=255), nullable=True),
        sa.Column("source_row_index", sa.Integer(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column(
            "bank_account_id",
            sa.String(length=36),
            sa.ForeignKey("bank_accounts.id"),
            nullable=True,
        ),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=True),
        sa.Column("debit_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("credit_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("counterparty_name", sa.String(length=255), nullable=True),
        sa.Column("counterparty_account_no_encrypted", sa.String(length=512), nullable=True),
        sa.Column("counterparty_bank_name", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("transaction_type", sa.String(length=255), nullable=True),
        sa.Column("bank_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("receipt_no", sa.String(length=128), nullable=True),
        sa.Column("raw_row_json", sa.JSON(), nullable=True),
        sa.Column("row_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "journal_preview_rows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversion_run_id",
            sa.String(length=36),
            sa.ForeignKey("conversion_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "bank_transaction_id",
            sa.String(length=36),
            sa.ForeignKey("bank_transactions.id"),
            nullable=True,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("output_values_json", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'needs_confirmation'"),
        ),
        sa.Column("exception_codes_json", sa.JSON(), nullable=True),
        sa.Column("matched_rule_versions_json", sa.JSON(), nullable=True),
        sa.Column("rule_trace_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "manual_adjustments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "journal_preview_row_id",
            sa.String(length=36),
            sa.ForeignKey("journal_preview_rows.id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "adjusted_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "confirmations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "journal_preview_row_id",
            sa.String(length=36),
            sa.ForeignKey("journal_preview_rows.id"),
            nullable=False,
        ),
        sa.Column("confirmation_type", sa.String(length=64), nullable=False),
        sa.Column(
            "confirmed_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_table(
        "exports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversion_run_id",
            sa.String(length=36),
            sa.ForeignKey("conversion_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "exported_by",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("report_storage_key", sa.String(length=512), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("only_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id"),
            nullable=True,
        ),
        sa.Column(
            "actor_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("exports")
    op.drop_table("confirmations")
    op.drop_table("manual_adjustments")
    op.drop_table("journal_preview_rows")
    op.drop_table("bank_transactions")
    op.drop_table("conversion_run_rule_versions")
    op.drop_table("conversion_run_files")
    op.drop_table("conversion_runs")
    op.drop_table("rule_versions")
    op.drop_table("rules")
    op.drop_table("mapping_profile_versions")
    op.drop_table("mapping_profiles")
    op.drop_table("company_journal_template_versions")
    op.drop_table("bank_template_versions")
    op.drop_table("company_journal_templates")
    op.drop_table("bank_templates")
    op.drop_table("source_files")
    op.drop_table("bank_accounts")
    op.drop_table("companies")
    op.drop_table("roles")
    op.drop_table("users")
