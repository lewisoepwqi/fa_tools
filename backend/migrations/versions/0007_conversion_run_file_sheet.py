"""conversion_run_files 记录每文件使用的 sheet 名（审计追溯）

sheet 是文件级属性（同一银行不同月份导出的工作表名可能不同），不再钉死在
模板上。本次转换每个文件实际用的 sheet 名落到 conversion_run_files，配合
bank_transactions.source_sheet_name（行级）实现完整追溯。

Revision ID: 0007_conversion_run_file_sheet
Revises: 0006_run_status_error
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_conversion_run_file_sheet"
down_revision = "0006_run_status_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversion_run_files",
        sa.Column("source_sheet_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversion_run_files", "source_sheet_name")
