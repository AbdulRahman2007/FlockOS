"""Add buyers, suppliers, sales, payments and farm expenses."""

import sqlalchemy as sa
from alembic import op

revision = "0007_sales_and_expenses"
down_revision = "0006_dashboard_finance_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("buyers", "suppliers"):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("phone", sa.String(40)),
            sa.Column("created_by", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "id", name=f"uq_{table}_tenant_id_id"),
            sa.UniqueConstraint("tenant_id", "name", name=f"uq_{table}_tenant_name"),
        )
        op.create_index(f"ix_{table}_tenant_name", table, ["tenant_id", "name"])

    op.rename_table("direct_costs", "expenses")
    op.drop_index("ix_direct_costs_tenant_farm_date", table_name="expenses")
    op.drop_index("ix_direct_costs_tenant_flock_date", table_name="expenses")
    op.drop_constraint("ck_direct_cost_positive", "expenses", type_="check")
    op.create_check_constraint("ck_expenses_amount_positive", "expenses", "amount_pkr > 0")
    op.alter_column("expenses", "flock_id", nullable=True)
    op.add_column("expenses", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.add_column(
        "expenses", sa.Column("scope", sa.String(16), server_default="direct", nullable=False)
    )
    op.add_column(
        "expenses", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column("expenses", sa.Column("updated_by", sa.Uuid(), nullable=True))
    op.execute("UPDATE expenses SET updated_by = created_by")
    op.alter_column("expenses", "updated_by", nullable=False)
    op.alter_column("expenses", "scope", server_default=None)
    op.alter_column("expenses", "version", server_default=None)
    op.create_foreign_key(
        "fk_expenses_tenant_supplier",
        "expenses",
        "suppliers",
        ["tenant_id", "supplier_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_expenses_tenant_updated_by",
        "expenses",
        "users",
        ["tenant_id", "updated_by"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint("ck_expenses_scope", "expenses", "scope IN ('direct', 'farm')")
    op.create_check_constraint(
        "ck_expenses_scope_flock",
        "expenses",
        "(scope = 'direct' AND flock_id IS NOT NULL) OR (scope = 'farm' AND flock_id IS NULL)",
    )
    op.create_check_constraint("ck_expenses_version_positive", "expenses", "version >= 1")
    op.create_index(
        "ix_expenses_tenant_farm_date", "expenses", ["tenant_id", "farm_id", "incurred_on"]
    )
    op.create_index(
        "ix_expenses_tenant_flock_date", "expenses", ["tenant_id", "flock_id", "incurred_on"]
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("flock_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("sale_on", sa.Date(), nullable=False),
        sa.Column("birds", sa.Integer(), nullable=False),
        sa.Column("total_weight_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("rate_per_kg_pkr", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_pkr", sa.Numeric(14, 2), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("birds > 0", name="ck_sales_birds_positive"),
        sa.CheckConstraint("total_weight_kg > 0", name="ck_sales_weight_positive"),
        sa.CheckConstraint("rate_per_kg_pkr >= 0", name="ck_sales_rate_nonnegative"),
        sa.CheckConstraint("amount_pkr >= 0", name="ck_sales_amount_nonnegative"),
        sa.CheckConstraint("version >= 1", name="ck_sales_version_positive"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "flock_id", "farm_id"],
            ["flocks.tenant_id", "flocks.id", "flocks.farm_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "buyer_id"], ["buyers.tenant_id", "buyers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_sales_tenant_id_id"),
    )
    op.create_index("ix_sales_tenant_farm_date", "sales", ["tenant_id", "farm_id", "sale_on"])
    op.create_index("ix_sales_tenant_flock_date", "sales", ["tenant_id", "flock_id", "sale_on"])
    op.create_index("ix_sales_tenant_buyer_date", "sales", ["tenant_id", "buyer_id", "sale_on"])
    op.create_table(
        "sale_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sale_id", sa.Uuid(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount_pkr", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(160)),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_pkr > 0", name="ck_sale_payments_amount_positive"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sale_payments_tenant_sale_date", "sale_payments", ["tenant_id", "sale_id", "paid_on"]
    )


def downgrade() -> None:
    op.drop_index("ix_sale_payments_tenant_sale_date", table_name="sale_payments")
    op.drop_table("sale_payments")
    for name in (
        "ix_sales_tenant_buyer_date",
        "ix_sales_tenant_flock_date",
        "ix_sales_tenant_farm_date",
    ):
        op.drop_index(name, table_name="sales")
    op.drop_table("sales")
    for name in ("ix_expenses_tenant_flock_date", "ix_expenses_tenant_farm_date"):
        op.drop_index(name, table_name="expenses")
    for name in (
        "ck_expenses_version_positive",
        "ck_expenses_scope_flock",
        "ck_expenses_scope",
    ):
        op.drop_constraint(name, "expenses", type_="check")
    op.drop_constraint("fk_expenses_tenant_updated_by", "expenses", type_="foreignkey")
    op.drop_constraint("fk_expenses_tenant_supplier", "expenses", type_="foreignkey")
    op.drop_column("expenses", "updated_by")
    op.drop_column("expenses", "version")
    op.drop_column("expenses", "scope")
    op.drop_column("expenses", "supplier_id")
    op.alter_column("expenses", "flock_id", nullable=False)
    op.drop_constraint("ck_expenses_amount_positive", "expenses", type_="check")
    op.create_check_constraint("ck_direct_cost_positive", "expenses", "amount_pkr > 0")
    op.rename_table("expenses", "direct_costs")
    op.create_index(
        "ix_direct_costs_tenant_farm_date", "direct_costs", ["tenant_id", "farm_id", "incurred_on"]
    )
    op.create_index(
        "ix_direct_costs_tenant_flock_date",
        "direct_costs",
        ["tenant_id", "flock_id", "incurred_on"],
    )
    for table in ("suppliers", "buyers"):
        op.drop_index(f"ix_{table}_tenant_name", table_name=table)
        op.drop_table(table)
