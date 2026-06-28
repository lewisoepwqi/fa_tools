"""builtin field overrides

Revision ID: 0003_builtin_field_overrides
Revises: 0002_custom_fields
Create Date: 2026-06-28 00:00:00.000000

- 公司级内置标准字段覆盖表（label / 识别关键词 / 规则操作符类型）
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_builtin_field_overrides"
down_revision = "0002_custom_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "builtin_field_overrides",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label_override", sa.String(length=64), nullable=True),
        sa.Column("header_keywords_override", sa.JSON(), nullable=True),
        sa.Column("type_override", sa.String(length=16), nullable=True),
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
        sa.UniqueConstraint(
            "company_id", "field_key", name="uq_builtin_overrides_company_field_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("builtin_field_overrides")
