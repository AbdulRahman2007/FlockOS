from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class FarmCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=500)
    timezone: str = Field(default="Asia/Karachi", min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def supported_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid IANA time zone") from None
        return value


class FarmUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def supported_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid IANA time zone") from None
        return value


class FarmRead(BaseModel):
    id: UUID
    name: str
    location: str | None
    timezone: str
    created_at: datetime
    updated_at: datetime


class ShedCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    capacity_birds: int | None = Field(default=None, gt=0)


class ShedUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    capacity_birds: int | None = Field(default=None, gt=0)


class ShedRead(BaseModel):
    id: UUID
    farm_id: UUID
    name: str
    capacity_birds: int | None
    created_at: datetime
    updated_at: datetime


class PlacementCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    placed_on: date
    bird_count: int = Field(gt=0)
    chick_source: str = Field(min_length=1, max_length=160)
    average_weight_kg: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)


class PlacementRead(BaseModel):
    id: UUID
    placed_on: date
    bird_count: int
    chick_source: str
    average_weight_kg: Decimal | None


class FlockCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    farm_id: UUID
    shed_id: UUID
    name: str = Field(min_length=1, max_length=120)
    placement: PlacementCreate


class FlockUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class FlockRead(BaseModel):
    id: UUID
    farm_id: UUID
    shed_id: UUID
    name: str
    status: str
    locked: bool
    placed_birds: int
    placements: list[PlacementRead]
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FlockListRead(BaseModel):
    id: UUID
    farm_id: UUID
    shed_id: UUID
    name: str
    status: str
    locked: bool
    placed_birds: int
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReopenFlockRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class FlockStatusRead(BaseModel):
    flock_id: UUID
    status: str
    locked: bool


class TenantSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feed_bag_size_kg: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=3)
    target_mortality_percent: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=6, decimal_places=3
    )
    target_fcr: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=3)
    manager_daily_window_days: int = Field(default=7, ge=1, le=30)
    worker_daily_window_days: int = Field(default=1, ge=1, le=30)


class TenantSettingsRead(BaseModel):
    feed_bag_size_kg: Decimal | None
    target_mortality_percent: Decimal | None
    target_fcr: Decimal | None
    manager_daily_window_days: int = 7
    worker_daily_window_days: int = 1
    updated_at: datetime | None
