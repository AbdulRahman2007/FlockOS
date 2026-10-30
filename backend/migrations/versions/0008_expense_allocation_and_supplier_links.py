"""Configurable eligible flock periods and supplier links for purchases."""

import sqlalchemy as sa
from alembic import op

revision = "0008_expense_alloc_links"
down_revision = "0007_sales_and_expenses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_expenses_tenant_id_id", "expenses", ["tenant_id", "id"])
    op.add_column("expenses", sa.Column("allocation_start", sa.Date(), nullable=True))
    op.add_column("expenses", sa.Column("allocation_end", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_expenses_allocation_period",
        "expenses",
        "(scope = 'direct' AND allocation_start IS NULL AND allocation_end IS NULL) OR "
        "(scope = 'farm' AND allocation_start IS NOT NULL AND allocation_end IS NOT NULL "
        "AND allocation_end >= allocation_start)",
    )
    op.create_table(
        "expense_eligible_flocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("flock_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "expense_id"], ["expenses.tenant_id", "expenses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "flock_id", "farm_id"],
            ["flocks.tenant_id", "flocks.id", "flocks.farm_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "expense_id", "flock_id", name="uq_expense_eligible_flock"
        ),
    )
    op.create_index(
        "ix_expense_eligible_tenant_flock", "expense_eligible_flocks", ["tenant_id", "flock_id"]
    )
    op.add_column("feed_purchases", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_feed_purchases_tenant_supplier",
        "feed_purchases",
        "suppliers",
        ["tenant_id", "supplier_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_feed_purchases_tenant_supplier", "feed_purchases", type_="foreignkey")
    op.drop_column("feed_purchases", "supplier_id")
    op.drop_index("ix_expense_eligible_tenant_flock", table_name="expense_eligible_flocks")
    op.drop_table("expense_eligible_flocks")
    op.drop_constraint("ck_expenses_allocation_period", "expenses", type_="check")
    op.drop_column("expenses", "allocation_end")
    op.drop_column("expenses", "allocation_start")
    op.drop_constraint("uq_expenses_tenant_id_id", "expenses", type_="unique")
