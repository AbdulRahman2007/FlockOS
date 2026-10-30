from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MarketPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_on: date
    price_per_kg_pkr: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class MarketPriceRead(BaseModel):
    id: UUID
    effective_on: date
    price_per_kg_pkr: Decimal
    created_at: datetime


class DirectCostCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    flock_id: UUID
    incurred_on: date
    amount_pkr: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    description: str = Field(min_length=1, max_length=240)


class DirectCostRead(BaseModel):
    id: UUID
    flock_id: UUID
    incurred_on: date
    amount_pkr: Decimal
    description: str
    created_at: datetime


class DashboardMetric(BaseModel):
    value: Decimal | int | None
    status: str


class DashboardAlert(BaseModel):
    kind: str
    farm_id: UUID
    flock_id: UUID | None = None
    message: str


class DashboardTrendPoint(BaseModel):
    day: date
    flock_id: UUID | None = None
    flock_name: str | None = None
    mortality_percent: Decimal | None = None
    feed_used_kg: Decimal | None = None
    average_weight_kg: Decimal | None = None
    target_weight_kg: Decimal | None = None


class DashboardRead(BaseModel):
    as_of: date
    metrics: dict[str, DashboardMetric]
    alerts: list[DashboardAlert]
    trends: list[DashboardTrendPoint]
    empty: bool
