"""Add effective market prices and flock direct-cost facts."""

import sqlalchemy as sa
from alembic import op

revision = "0006_dashboard_finance_facts"
down_revision = "0005_configurable_daily_windows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_flocks_tenant_id_farm_id", "flocks", ["tenant_id", "id", "farm_id"]
    )
    op.create_table(
        "market_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("price_per_kg_pkr", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price_per_kg_pkr >= 0", name="ck_market_price_nonnegative"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_prices_tenant_farm_effective",
        "market_prices",
        ["tenant_id", "farm_id", "effective_on"],
    )
    op.create_table(
        "direct_costs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("flock_id", sa.Uuid(), nullable=False),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("amount_pkr", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_pkr > 0", name="ck_direct_cost_positive"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "flock_id", "farm_id"],
            ["flocks.tenant_id", "flocks.id", "flocks.farm_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_direct_costs_tenant_farm_date", "direct_costs", ["tenant_id", "farm_id", "incurred_on"]
    )
    op.create_index(
        "ix_direct_costs_tenant_flock_date",
        "direct_costs",
        ["tenant_id", "flock_id", "incurred_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_direct_costs_tenant_flock_date", table_name="direct_costs")
    op.drop_index("ix_direct_costs_tenant_farm_date", table_name="direct_costs")
    op.drop_table("direct_costs")
    op.drop_index("ix_market_prices_tenant_farm_effective", table_name="market_prices")
    op.drop_table("market_prices")
    op.drop_constraint("uq_flocks_tenant_id_farm_id", "flocks", type_="unique")
