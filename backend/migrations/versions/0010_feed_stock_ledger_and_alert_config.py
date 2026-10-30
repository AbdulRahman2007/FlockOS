"""Add farm feed-stock facts and tenant alert/weight defaults."""

from alembic import op
import sqlalchemy as sa

revision = "0010_feed_stock_ledger_and_alert_config"
down_revision = "0009_daily_record_report_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column(
            "high_daily_mortality_percent",
            sa.Numeric(6, 3),
            nullable=False,
            server_default="0.5",
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "early_daily_mortality_percent",
            sa.Numeric(6, 3),
            nullable=False,
            server_default="1.0",
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column("early_mortality_days", sa.Integer(), nullable=False, server_default="7"),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "feed_cover_threshold_days",
            sa.Numeric(6, 2),
            nullable=False,
            server_default="3",
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "feed_cover_usage_window_days", sa.Integer(), nullable=False, server_default="3"
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "fcr_tolerance_percent", sa.Numeric(6, 3), nullable=False, server_default="5"
        ),
    )
    op.create_check_constraint(
        "ck_tenant_settings_daily_mortality_percent",
        "tenant_settings",
        "high_daily_mortality_percent BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tenant_settings_early_mortality_percent",
        "tenant_settings",
        "early_daily_mortality_percent BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tenant_settings_early_mortality_days",
        "tenant_settings",
        "early_mortality_days BETWEEN 1 AND 30",
    )
    op.create_check_constraint(
        "ck_tenant_settings_feed_cover_threshold_positive",
        "tenant_settings",
        "feed_cover_threshold_days > 0",
    )
    op.create_check_constraint(
        "ck_tenant_settings_feed_cover_window",
        "tenant_settings",
        "feed_cover_usage_window_days BETWEEN 1 AND 30",
    )
    op.create_check_constraint(
        "ck_tenant_settings_fcr_tolerance_percent",
        "tenant_settings",
        "fcr_tolerance_percent BETWEEN 0 AND 100",
    )

    op.create_table(
        "feed_stock_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("quantity_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('opening', 'return_to_stock', 'return_to_supplier', 'adjustment')",
            name="ck_feed_stock_event_type",
        ),
        sa.CheckConstraint(
            "(event_type = 'opening' AND quantity_kg >= 0) OR "
            "(event_type IN ('return_to_stock', 'return_to_supplier') AND quantity_kg > 0) OR "
            "(event_type = 'adjustment' AND quantity_kg <> 0)",
            name="ck_feed_stock_event_quantity",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_feed_stock_opening_per_farm",
        "feed_stock_events",
        ["tenant_id", "farm_id"],
        unique=True,
        postgresql_where=sa.text("event_type = 'opening'"),
        sqlite_where=sa.text("event_type = 'opening'"),
    )
    op.create_index(
        "ix_feed_stock_events_tenant_farm_date",
        "feed_stock_events",
        ["tenant_id", "farm_id", "occurred_on"],
    )

    op.create_table(
        "tenant_weight_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("age_day", sa.Integer(), nullable=False),
        sa.Column("average_weight_kg", sa.Numeric(8, 3), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("age_day > 0", name="ck_tenant_weight_target_age_positive"),
        sa.CheckConstraint(
            "average_weight_kg > 0", name="ck_tenant_weight_target_weight_positive"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_tenant_weight_target_tenant_updated_by",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "age_day", name="uq_tenant_weight_target_age"),
    )
    op.create_index(
        "ix_tenant_weight_targets_tenant_age", "tenant_weight_targets", ["tenant_id", "age_day"]
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_weight_targets_tenant_age", table_name="tenant_weight_targets")
    op.drop_table("tenant_weight_targets")
    op.drop_index("ix_feed_stock_events_tenant_farm_date", table_name="feed_stock_events")
    op.drop_index("uq_feed_stock_opening_per_farm", table_name="feed_stock_events")
    op.drop_table("feed_stock_events")
    op.drop_constraint(
        "ck_tenant_settings_fcr_tolerance_percent", "tenant_settings", type_="check"
    )
    op.drop_constraint("ck_tenant_settings_feed_cover_window", "tenant_settings", type_="check")
    op.drop_constraint(
        "ck_tenant_settings_feed_cover_threshold_positive", "tenant_settings", type_="check"
    )
    op.drop_constraint(
        "ck_tenant_settings_early_mortality_days", "tenant_settings", type_="check"
    )
    op.drop_constraint(
        "ck_tenant_settings_early_mortality_percent", "tenant_settings", type_="check"
    )
    op.drop_constraint(
        "ck_tenant_settings_daily_mortality_percent", "tenant_settings", type_="check"
    )
    op.drop_column("tenant_settings", "fcr_tolerance_percent")
    op.drop_column("tenant_settings", "feed_cover_usage_window_days")
    op.drop_column("tenant_settings", "feed_cover_threshold_days")
    op.drop_column("tenant_settings", "early_mortality_days")
    op.drop_column("tenant_settings", "early_daily_mortality_percent")
    op.drop_column("tenant_settings", "high_daily_mortality_percent")
