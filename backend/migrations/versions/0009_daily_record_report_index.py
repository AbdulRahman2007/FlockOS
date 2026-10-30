"""Add tenant-date index for date-range daily-record reports.

Revision ID: 0009_daily_record_report_index
Revises: 0008_expense_alloc_links
Create Date: 2026-10-27
"""

from __future__ import annotations

from alembic import op

revision = "0009_daily_record_report_index"
down_revision = "0008_expense_alloc_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_daily_tenant_date_flock",
        "daily_records",
        ["tenant_id", "record_date", "flock_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_tenant_date_flock", table_name="daily_records")
