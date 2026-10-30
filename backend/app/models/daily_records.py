from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyRecord(Base):
    __tablename__ = "daily_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "flock_id", "record_date", name="uq_daily_flock_date"),
        UniqueConstraint(
            "tenant_id", "created_by", "idempotency_key", name="uq_daily_idempotency_key"
        ),
        Index("ix_daily_tenant_date_flock", "tenant_id", "record_date", "flock_id"),
        ForeignKeyConstraint(
            ["tenant_id", "flock_id"], ["flocks.tenant_id", "flocks.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("deaths >= 0", name="ck_daily_deaths_nonnegative"),
        CheckConstraint("culling >= 0", name="ck_daily_culling_nonnegative"),
        CheckConstraint("feed_used_kg >= 0", name="ck_daily_feed_nonnegative"),
        CheckConstraint("water_liters >= 0", name="ck_daily_water_nonnegative"),
        CheckConstraint("temperature_c >= -10 AND temperature_c <= 60", name="ck_daily_temp_range"),
        CheckConstraint("version >= 1", name="ck_daily_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    flock_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, nullable=False)
    culling: Mapped[int] = mapped_column(Integer, nullable=False)
    feed_used_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    water_liters: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    temperature_c: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __mapper_args__ = {"version_id_col": version}


class WeightSample(Base):
    __tablename__ = "weight_samples"
    __table_args__ = (
        UniqueConstraint("tenant_id", "flock_id", "sampled_on", name="uq_weight_flock_date"),
        ForeignKeyConstraint(
            ["tenant_id", "flock_id"], ["flocks.tenant_id", "flocks.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("sample_size > 0", name="ck_weight_sample_size_positive"),
        CheckConstraint("average_weight_kg >= 0", name="ck_weight_average_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    flock_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sampled_on: Mapped[date] = mapped_column(Date, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    average_weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedPurchase(Base):
    __tablename__ = "feed_purchases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["suppliers.tenant_id", "suppliers.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_feed_purchase_quantity_positive"),
        CheckConstraint("quantity_kg > 0", name="ck_feed_purchase_kg_positive"),
        CheckConstraint("unit IN ('kg', 'bags')", name="ck_feed_purchase_unit"),
        CheckConstraint(
            "unit = 'kg' OR bag_size_kg IS NOT NULL", name="ck_feed_purchase_bag_size_required"
        ),
        CheckConstraint(
            "amount_pkr IS NULL OR amount_pkr >= 0", name="ck_feed_purchase_amount_nonnegative"
        ),
        Index("ix_feed_purchase_tenant_farm_date", "tenant_id", "farm_id", "purchased_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    purchased_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    bag_size_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    amount_pkr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    supplier_name: Mapped[str | None] = mapped_column(String(160))
    supplier_id: Mapped[UUID | None] = mapped_column(Uuid)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedStockEvent(Base):
    """Audited opening, return, and adjustment facts for farm feed inventory."""

    __tablename__ = "feed_stock_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint(
            "event_type IN ('opening', 'return_to_stock', 'return_to_supplier', 'adjustment')",
            name="ck_feed_stock_event_type",
        ),
        CheckConstraint(
            "(event_type = 'opening' AND quantity_kg >= 0) OR "
            "(event_type IN ('return_to_stock', 'return_to_supplier') AND quantity_kg > 0) OR "
            "(event_type = 'adjustment' AND quantity_kg <> 0)",
            name="ck_feed_stock_event_quantity",
        ),
        Index(
            "uq_feed_stock_opening_per_farm",
            "tenant_id",
            "farm_id",
            unique=True,
            postgresql_where=text("event_type = 'opening'"),
            sqlite_where=text("event_type = 'opening'"),
        ),
        Index("ix_feed_stock_events_tenant_farm_date", "tenant_id", "farm_id", "occurred_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
