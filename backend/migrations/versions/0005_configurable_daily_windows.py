"""Add tenant-configurable daily record edit windows.

Revision ID: 0005_configurable_daily_windows
Revises: 0004_daily_operations
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_configurable_daily_windows"
down_revision = "0004_daily_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("manager_daily_window_days", sa.Integer(), server_default="7", nullable=False),
    )
    op.add_column(
        "tenant_settings",
        sa.Column("worker_daily_window_days", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_tenant_settings_manager_daily_window",
        "tenant_settings",
        "manager_daily_window_days BETWEEN 1 AND 30",
    )
    op.create_check_constraint(
        "ck_tenant_settings_worker_daily_window",
        "tenant_settings",
        "worker_daily_window_days BETWEEN 1 AND 30",
    )
    op.alter_column("tenant_settings", "manager_daily_window_days", server_default=None)
    op.alter_column("tenant_settings", "worker_daily_window_days", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_tenant_settings_worker_daily_window", "tenant_settings", type_="check")
    op.drop_constraint("ck_tenant_settings_manager_daily_window", "tenant_settings", type_="check")
    op.drop_column("tenant_settings", "worker_daily_window_days")
    op.drop_column("tenant_settings", "manager_daily_window_days")
