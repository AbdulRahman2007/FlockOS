from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PartyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)


class PartyRead(PartyCreate):
    id: UUID


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    flock_id: UUID | None = None
    supplier_id: UUID | None = None
    scope: str
    incurred_on: date
    allocation_start: date | None = None
    allocation_end: date | None = None
    eligible_flock_ids: list[UUID] = Field(default_factory=list, max_length=100)
    amount_pkr: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    description: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_allocation(self) -> "ExpenseCreate":
        if self.scope == "direct":
            if (
                self.flock_id is None
                or self.allocation_start
                or self.allocation_end
                or self.eligible_flock_ids
            ):
                raise ValueError(
                    "Direct expenses require a flock and cannot have an allocation period"
                )
        elif self.scope == "farm":
            if (
                self.flock_id is not None
                or self.allocation_start is None
                or self.allocation_end is None
            ):
                raise ValueError("Farm expenses need an allocation period and no direct flock")
            if self.allocation_end < self.allocation_start or not self.eligible_flock_ids:
                raise ValueError("Choose eligible flocks and a valid allocation period")
            if len(set(self.eligible_flock_ids)) != len(self.eligible_flock_ids):
                raise ValueError("Eligible flock IDs must be unique")
        else:
            raise ValueError("Expense scope must be direct or farm")
        return self


class ExpenseUpdate(ExpenseCreate):
    expected_version: int = Field(ge=1)


class SaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flock_id: UUID
    buyer_id: UUID
    sale_on: date
    birds: int = Field(gt=0)
    total_weight_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    rate_per_kg_pkr: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    amount_pkr: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    amount_paid_pkr: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)


class SaleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    buyer_id: UUID
    sale_on: date
    birds: int = Field(gt=0)
    total_weight_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    rate_per_kg_pkr: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    amount_pkr: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class SaleRead(BaseModel):
    id: UUID
    flock_id: UUID
    buyer_id: UUID
    sale_on: date
    birds: int
    total_weight_kg: Decimal
    rate_per_kg_pkr: Decimal
    amount_pkr: Decimal
    version: int
    created_at: datetime


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paid_on: date
    amount_pkr: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reference: str | None = Field(default=None, max_length=160)


class FlockProfitRead(BaseModel):
    flock_id: UUID
    as_of: date
    live_birds: int
    estimated_profit_pkr: Decimal | None
    actual_profit_pkr: Decimal
    direct_costs_pkr: Decimal
    allocated_farm_costs_pkr: Decimal
    status: str
