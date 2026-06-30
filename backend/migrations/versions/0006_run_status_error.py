"""转换批次 error_message 列（RunStatus 状态机支撑）

Revision ID: 0006_run_status_error
Revises: 0005_auth_rbac
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_run_status_error"
down_revision = "0005_auth_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversion_runs", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversion_runs", "error_message")
