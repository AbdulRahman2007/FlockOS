from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DailyRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_date: date
    deaths: int = Field(ge=0)
    culling: int = Field(ge=0)
    feed_used_kg: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    water_liters: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    temperature_c: Decimal = Field(ge=-10, le=60, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class DailyRecordUpdate(DailyRecordCreate):
    expected_version: int = Field(ge=1)


class DailyRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flock_id: UUID
    record_date: date
    deaths: int
    culling: int
    feed_used_kg: Decimal
    water_liters: Decimal
    temperature_c: Decimal
    notes: str | None
    version: int
    closing_birds: int | None = None
    created_by: UUID
    updated_at: datetime


class DailyRecordList(BaseModel):
    items: list[DailyRecordRead]
    missing_dates: list[date]
    total: int
    limit: int
    offset: int


class WeightSampleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sampled_on: date
    sample_size: int = Field(gt=0)
    average_weight_kg: Decimal = Field(ge=0, max_digits=12, decimal_places=3)


class WeightSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    flock_id: UUID
    sampled_on: date
    sample_size: int
    average_weight_kg: Decimal
    created_by: UUID
    created_at: datetime


class FeedPurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchased_on: date
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(pattern="^(kg|bags)$")
    amount_pkr: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    supplier_name: str | None = Field(default=None, max_length=160)
    supplier_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class FeedPurchaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    purchased_on: date
    quantity: Decimal
    unit: str
    bag_size_kg: Decimal | None
    quantity_kg: Decimal
    amount_pkr: Decimal | None
    supplier_name: str | None
    supplier_id: UUID | None
    notes: str | None
    created_by: UUID
    created_at: datetime
