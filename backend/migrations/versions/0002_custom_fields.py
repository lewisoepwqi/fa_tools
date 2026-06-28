"""custom fields + bank_transactions ext columns

Revision ID: 0002_custom_fields
Revises: 0001_initial_schema
Create Date: 2026-06-28 00:00:00.000000

- bank_transactions 预分配中性扩展列（8 文本 / 4 金额 / 2 日期）
- 新建 custom_fields 表（公司级扩展字段定义）
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_custom_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

# 预分配扩展列（与 BankTransaction 模型一一对应）
EXT_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("ext_text_1", sa.String(length=255)),
    ("ext_text_2", sa.String(length=255)),
    ("ext_text_3", sa.String(length=255)),
    ("ext_text_4", sa.String(length=255)),
    ("ext_text_5", sa.String(length=255)),
    ("ext_text_6", sa.String(length=255)),
    ("ext_text_7", sa.String(length=255)),
    ("ext_text_8", sa.String(length=255)),
    ("ext_amount_1", sa.Numeric(precision=18, scale=2)),
    ("ext_amount_2", sa.Numeric(precision=18, scale=2)),
    ("ext_amount_3", sa.Numeric(precision=18, scale=2)),
    ("ext_amount_4", sa.Numeric(precision=18, scale=2)),
    ("ext_date_1", sa.Date()),
    ("ext_date_2", sa.Date()),
]


def upgrade() -> None:
    # 1) bank_transactions 预分配中性扩展列
    for col_name, col_type in EXT_COLUMNS:
        op.add_column(
            "bank_transactions",
            sa.Column(col_name, col_type, nullable=True),
        )

    # 2) 公司级自定义扩展字段定义表
    op.create_table(
        "custom_fields",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slot_key", sa.String(length=32), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("header_keywords_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint(
            "company_id", "field_key", name="uq_custom_fields_company_field_key"
        ),
        sa.UniqueConstraint("company_id", "slot_key", name="uq_custom_fields_company_slot_key"),
    )


def downgrade() -> None:
    op.drop_table("custom_fields")
    for col_name, _ in reversed(EXT_COLUMNS):
        op.drop_column("bank_transactions", col_name)
