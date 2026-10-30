"""Daily records, feed purchases, and flock weight samples.

Revision ID: 0004_daily_operations
Revises: 0003_farm_operations
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_daily_operations"
down_revision = "0003_farm_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "daily_records",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("flock_id", uuid_type, nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("deaths", sa.Integer(), nullable=False),
        sa.Column("culling", sa.Integer(), nullable=False),
        sa.Column("feed_used_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("water_liters", sa.Numeric(12, 2), nullable=False),
        sa.Column("temperature_c", sa.Numeric(5, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", uuid_type, nullable=False),
        sa.Column("updated_by", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "flock_id", "record_date", name="uq_daily_flock_date"),
        sa.UniqueConstraint(
            "tenant_id", "created_by", "idempotency_key", name="uq_daily_idempotency_key"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "flock_id"], ["flocks.tenant_id", "flocks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("deaths >= 0", name="ck_daily_deaths_nonnegative"),
        sa.CheckConstraint("culling >= 0", name="ck_daily_culling_nonnegative"),
        sa.CheckConstraint("feed_used_kg >= 0", name="ck_daily_feed_nonnegative"),
        sa.CheckConstraint("water_liters >= 0", name="ck_daily_water_nonnegative"),
        sa.CheckConstraint(
            "temperature_c >= -10 AND temperature_c <= 60", name="ck_daily_temp_range"
        ),
        sa.CheckConstraint("version >= 1", name="ck_daily_version_positive"),
    )
    op.create_table(
        "weight_samples",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("flock_id", uuid_type, nullable=False),
        sa.Column("sampled_on", sa.Date(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("average_weight_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("created_by", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "flock_id", "sampled_on", name="uq_weight_flock_date"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "flock_id"], ["flocks.tenant_id", "flocks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("sample_size > 0", name="ck_weight_sample_size_positive"),
        sa.CheckConstraint("average_weight_kg >= 0", name="ck_weight_average_nonnegative"),
    )
    op.create_table(
        "feed_purchases",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("farm_id", uuid_type, nullable=False),
        sa.Column("purchased_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("bag_size_kg", sa.Numeric(8, 3)),
        sa.Column("quantity_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("amount_pkr", sa.Numeric(14, 2)),
        sa.Column("supplier_name", sa.String(160)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_feed_purchase_quantity_positive"),
        sa.CheckConstraint("quantity_kg > 0", name="ck_feed_purchase_kg_positive"),
        sa.CheckConstraint("unit IN ('kg', 'bags')", name="ck_feed_purchase_unit"),
        sa.CheckConstraint(
            "unit = 'kg' OR bag_size_kg IS NOT NULL", name="ck_feed_purchase_bag_size_required"
        ),
        sa.CheckConstraint(
            "amount_pkr IS NULL OR amount_pkr >= 0", name="ck_feed_purchase_amount_nonnegative"
        ),
    )
    op.create_index(
        "ix_feed_purchase_tenant_farm_date",
        "feed_purchases",
        ["tenant_id", "farm_id", "purchased_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_feed_purchase_tenant_farm_date", table_name="feed_purchases")
    op.drop_table("feed_purchases")
    op.drop_table("weight_samples")
    op.drop_table("daily_records")
