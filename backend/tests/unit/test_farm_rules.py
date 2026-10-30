from collections.abc import Callable
from decimal import Decimal

import pytest

from app.domain.farm_rules import (
    close_flock,
    reopen_flock,
    validate_bag_size,
    validate_fcr_target,
    validate_mortality_target,
    validate_placement,
)


@pytest.mark.parametrize(
    ("bird_count", "capacity", "already_placed", "valid"),
    [(100, 100, 0, True), (1, 100, 99, True), (2, 100, 99, False), (1, None, 500, True)],
)
def test_placement_capacity_rules(
    bird_count: int, capacity: int | None, already_placed: int, valid: bool
) -> None:
    if valid:
        validate_placement(bird_count, capacity, already_placed)
    else:
        with pytest.raises(ValueError, match="capacity"):
            validate_placement(bird_count, capacity, already_placed)


@pytest.mark.parametrize(
    ("validator", "value"),
    [
        (validate_bag_size, Decimal("0")),
        (validate_mortality_target, Decimal("100.001")),
        (validate_fcr_target, Decimal("0")),
    ],
)
def test_settings_rules_reject_invalid_values(
    validator: Callable[[Decimal | None], None], value: Decimal
) -> None:
    with pytest.raises(ValueError):
        validator(value)


def test_closed_flock_is_locked_until_reopened() -> None:
    closed = close_flock("active")
    assert closed.status == "closed"
    assert closed.closed_at is not None
    reopened = reopen_flock(closed.status)
    assert reopened.status == "active"
    assert reopened.closed_at is None

    with pytest.raises(ValueError, match="active"):
        close_flock("closed")
