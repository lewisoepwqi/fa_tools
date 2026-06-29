"""add hot-path indexes

Revision ID: 0004_add_indexes
Revises: 0003_builtin_field_overrides
"""

from alembic import op

revision = "0004_add_indexes"
down_revision = "0003_builtin_field_overrides"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_journal_preview_rows_conversion_run_id", "journal_preview_rows", ["conversion_run_id"]),
    ("ix_bank_transactions_conversion_run_id", "bank_transactions", ["conversion_run_id"]),
    ("ix_bank_transactions_row_hash", "bank_transactions", ["row_hash"]),
    ("ix_conversion_run_files_conversion_run_id", "conversion_run_files", ["conversion_run_id"]),
    (
        "ix_conversion_run_rule_versions_conversion_run_id",
        "conversion_run_rule_versions",
        ["conversion_run_id"],
    ),
    ("ix_conversion_runs_company_id", "conversion_runs", ["company_id"]),
    (
        "ix_bank_template_versions_parent_ver",
        "bank_template_versions",
        ["bank_template_id", "version_no"],
    ),
    (
        "ix_company_journal_template_versions_parent_ver",
        "company_journal_template_versions",
        ["company_journal_template_id", "version_no"],
    ),
    (
        "ix_mapping_profile_versions_parent_ver",
        "mapping_profile_versions",
        ["mapping_profile_id", "version_no"],
    ),
    ("ix_rule_versions_parent_ver", "rule_versions", ["rule_id", "version_no"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
