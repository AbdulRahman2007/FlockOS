from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

FeedStockEventType = Literal[
    "opening", "return_to_stock", "return_to_supplier", "adjustment"
]


class FeedStockEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_type: FeedStockEventType
    occurred_on: date
    quantity_kg: Decimal = Field(max_digits=12, decimal_places=3)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_quantity_and_reason(self) -> "FeedStockEventCreate":
        if self.event_type == "adjustment":
            if self.quantity_kg == 0:
                raise ValueError("Adjustment quantity must not be zero")
            if not self.reason:
                raise ValueError("A reason is required for stock adjustments")
        elif self.event_type == "opening":
            if self.quantity_kg < 0:
                raise ValueError("Opening stock cannot be negative")
        elif self.quantity_kg <= 0:
            raise ValueError("Return quantity must be greater than zero")
        return self


class FeedStockEventRead(BaseModel):
    id: UUID
    occurred_on: date
    event_type: str
    quantity_kg: Decimal
    reason: str | None
    created_by: UUID
    created_at: datetime | None = None


class FeedStockEventItem(BaseModel):
    id: UUID
    occurred_on: date
    event_type: str
    quantity_kg: Decimal
    reason: str | None = None
    created_by: UUID


class FeedStockEventPage(BaseModel):
    items: list[FeedStockEventItem]
    total: int
    limit: int
    offset: int


class FeedStockSnapshotRead(BaseModel):
    farm_id: UUID
    as_of: date
    stock_kg: Decimal | None
    feed_cover_days: Decimal | None
    status: str
