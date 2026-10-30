from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Farm(Base):
    __tablename__ = "farms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_farms_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_farms_tenant_name"),
        Index("ix_farms_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Karachi")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Shed(Base):
    __tablename__ = "sheds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_sheds_tenant_id_id"),
        UniqueConstraint("tenant_id", "id", "farm_id", name="uq_sheds_tenant_id_farm"),
        UniqueConstraint("tenant_id", "farm_id", "name", name="uq_sheds_farm_name"),
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"],
            ["farms.tenant_id", "farms.id"],
            ondelete="RESTRICT",
            name="fk_sheds_tenant_farm",
        ),
        CheckConstraint(
            "capacity_birds IS NULL OR capacity_birds > 0", name="ck_sheds_capacity_positive"
        ),
        Index("ix_sheds_tenant_farm_name", "tenant_id", "farm_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity_birds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Flock(Base):
    __tablename__ = "flocks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_flocks_tenant_id_id"),
        UniqueConstraint("tenant_id", "id", "farm_id", name="uq_flocks_tenant_id_farm_id"),
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"],
            ["farms.tenant_id", "farms.id"],
            ondelete="RESTRICT",
            name="fk_flocks_tenant_farm",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "shed_id", "farm_id"],
            ["sheds.tenant_id", "sheds.id", "sheds.farm_id"],
            ondelete="RESTRICT",
            name="fk_flocks_tenant_shed_farm",
        ),
        CheckConstraint("status IN ('active', 'closed')", name="ck_flocks_status"),
        CheckConstraint(
            "(status = 'active' AND closed_at IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL)",
            name="ck_flocks_closed_timestamp",
        ),
        Index(
            "uq_flocks_one_active_per_shed",
            "tenant_id",
            "shed_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_flocks_tenant_farm_status", "tenant_id", "farm_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    shed_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FlockPlacement(Base):
    __tablename__ = "flock_placements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "flock_id"],
            ["flocks.tenant_id", "flocks.id"],
            ondelete="CASCADE",
            name="fk_flock_placements_tenant_flock",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_placements_tenant_created_by",
        ),
        CheckConstraint("bird_count > 0", name="ck_flock_placements_birds_positive"),
        CheckConstraint(
            "average_weight_kg IS NULL OR average_weight_kg >= 0",
            name="ck_flock_placements_weight_nonnegative",
        ),
        Index("ix_flock_placements_tenant_flock_date", "tenant_id", "flock_id", "placed_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    flock_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    placed_on: Mapped[date] = mapped_column(Date, nullable=False)
    bird_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chick_source: Mapped[str] = mapped_column(String(160), nullable=False)
    average_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TenantSettings(Base):
    __tablename__ = "tenant_settings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_tenant_settings_tenant_updated_by",
        ),
        CheckConstraint(
            "feed_bag_size_kg IS NULL OR feed_bag_size_kg > 0",
            name="ck_tenant_settings_bag_size_positive",
        ),
        CheckConstraint(
            "target_mortality_percent IS NULL OR "
            "(target_mortality_percent >= 0 AND target_mortality_percent <= 100)",
            name="ck_tenant_settings_mortality_percent",
        ),
        CheckConstraint(
            "target_fcr IS NULL OR target_fcr > 0", name="ck_tenant_settings_fcr_positive"
        ),
        CheckConstraint(
            "manager_daily_window_days BETWEEN 1 AND 30",
            name="ck_tenant_settings_manager_daily_window",
        ),
        CheckConstraint(
            "worker_daily_window_days BETWEEN 1 AND 30",
            name="ck_tenant_settings_worker_daily_window",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    feed_bag_size_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    target_mortality_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    target_fcr: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    manager_daily_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    worker_daily_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("price_per_kg_pkr >= 0", name="ck_market_price_nonnegative"),
        Index("ix_market_prices_tenant_farm_effective", "tenant_id", "farm_id", "effective_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    price_per_kg_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_suppliers_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_suppliers_tenant_name"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        Index("ix_suppliers_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Buyer(Base):
    __tablename__ = "buyers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_buyers_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_buyers_tenant_name"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        Index("ix_buyers_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_expenses_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "flock_id", "farm_id"],
            ["flocks.tenant_id", "flocks.id", "flocks.farm_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["suppliers.tenant_id", "suppliers.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("amount_pkr > 0", name="ck_expenses_amount_positive"),
        CheckConstraint("scope IN ('direct', 'farm')", name="ck_expenses_scope"),
        CheckConstraint(
            "(scope = 'direct' AND flock_id IS NOT NULL) OR (scope = 'farm' AND flock_id IS NULL)",
            name="ck_expenses_scope_flock",
        ),
        CheckConstraint(
            "(scope = 'direct' AND allocation_start IS NULL AND allocation_end IS NULL) OR "
            "(scope = 'farm' AND allocation_start IS NOT NULL AND allocation_end IS NOT NULL "
            "AND allocation_end >= allocation_start)",
            name="ck_expenses_allocation_period",
        ),
        CheckConstraint("version >= 1", name="ck_expenses_version_positive"),
        Index("ix_expenses_tenant_farm_date", "tenant_id", "farm_id", "incurred_on"),
        Index("ix_expenses_tenant_flock_date", "tenant_id", "flock_id", "incurred_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    flock_id: Mapped[UUID | None] = mapped_column(Uuid)
    supplier_id: Mapped[UUID | None] = mapped_column(Uuid)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="direct")
    incurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    allocation_start: Mapped[date | None] = mapped_column(Date)
    allocation_end: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)

    __mapper_args__ = {"version_id_col": version}


# Existing dashboard call sites use this name for direct flock expenses.
DirectCost = Expense


class ExpenseEligibleFlock(Base):
    __tablename__ = "expense_eligible_flocks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "expense_id"], ["expenses.tenant_id", "expenses.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "flock_id", "farm_id"],
            ["flocks.tenant_id", "flocks.id", "flocks.farm_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "expense_id", "flock_id", name="uq_expense_eligible_flock"),
        Index("ix_expense_eligible_tenant_flock", "tenant_id", "flock_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    expense_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    flock_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_sales_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "farm_id"], ["farms.tenant_id", "farms.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "flock_id", "farm_id"],
            ["flocks.tenant_id", "flocks.id", "flocks.farm_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "buyer_id"], ["buyers.tenant_id", "buyers.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("birds > 0", name="ck_sales_birds_positive"),
        CheckConstraint("total_weight_kg > 0", name="ck_sales_weight_positive"),
        CheckConstraint("rate_per_kg_pkr >= 0", name="ck_sales_rate_nonnegative"),
        CheckConstraint("amount_pkr >= 0", name="ck_sales_amount_nonnegative"),
        CheckConstraint("version >= 1", name="ck_sales_version_positive"),
        Index("ix_sales_tenant_farm_date", "tenant_id", "farm_id", "sale_on"),
        Index("ix_sales_tenant_flock_date", "tenant_id", "flock_id", "sale_on"),
        Index("ix_sales_tenant_buyer_date", "tenant_id", "buyer_id", "sale_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    farm_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    flock_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    buyer_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sale_on: Mapped[date] = mapped_column(Date, nullable=False)
    birds: Mapped[int] = mapped_column(Integer, nullable=False)
    total_weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    rate_per_kg_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __mapper_args__ = {"version_id_col": version}


class SalePayment(Base):
    __tablename__ = "sale_payments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["users.tenant_id", "users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("amount_pkr > 0", name="ck_sale_payments_amount_positive"),
        Index("ix_sale_payments_tenant_sale_date", "tenant_id", "sale_id", "paid_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    sale_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160))
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
