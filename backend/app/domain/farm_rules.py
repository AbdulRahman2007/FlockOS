from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal


@dataclass(frozen=True)
class FlockStatusChange:
    status: str
    closed_at: datetime | None


def validate_placement(
    bird_count: int, capacity_birds: int | None, already_placed: int = 0
) -> None:
    if bird_count <= 0:
        raise ValueError("Placement must include at least one bird")
    if already_placed < 0:
        raise ValueError("Existing placement count cannot be negative")
    if capacity_birds is not None and already_placed + bird_count > capacity_birds:
        raise ValueError("Placement exceeds the shed capacity")


def validate_bag_size(value: Decimal | None) -> None:
    if value is not None and value <= 0:
        raise ValueError("Feed bag size must be greater than zero")


def validate_mortality_target(value: Decimal | None) -> None:
    if value is not None and not Decimal(0) <= value <= Decimal(100):
        raise ValueError("Target mortality must be between 0 and 100 percent")


def validate_fcr_target(value: Decimal | None) -> None:
    if value is not None and value <= 0:
        raise ValueError("Target FCR must be greater than zero")


def close_flock(status: str) -> FlockStatusChange:
    if status != "active":
        raise ValueError("Only an active flock can be closed")
    return FlockStatusChange(status="closed", closed_at=datetime.now(UTC))


def reopen_flock(status: str) -> FlockStatusChange:
    if status != "closed":
        raise ValueError("Only a closed flock can be reopened")
    return FlockStatusChange(status="active", closed_at=None)
