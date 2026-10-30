"""Pure Decimal calculations for the poultry facts ledger.

Inputs are already normalized facts in farm-local business-date order. This
module does not read persistence, apply display rounding, or choose event order
within a day. Callers aggregate same-day facts before calculating balances.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class DailyBirdFacts:
    """Daily count movements after same-day facts have been aggregated."""

    day: date
    deaths: int = 0
    culling: int = 0
    sold: int = 0
    transferred_out: int = 0
    transferred_in: int = 0


@dataclass(frozen=True)
class DailyBirdBalance:
    day: date
    opening_birds: int
    deaths: int
    culling: int
    sold: int
    transferred_out: int
    transferred_in: int
    closing_birds: int


@dataclass(frozen=True)
class FlockFcrInputs:
    cumulative_feed_kg: Decimal
    sold_live_weight_kg: Decimal
    dead_bird_weight_kg: Decimal
    placement_biomass_kg: Decimal
    current_birds_alive: int = 0
    latest_average_weight_kg: Decimal | None = None


@dataclass(frozen=True)
class FeedMetrics:
    total_used_kg: Decimal
    bag_equivalent: Decimal


@dataclass(frozen=True)
class ProfitResult:
    estimated_profit_pkr: Decimal
    actual_profit_pkr: Decimal


@dataclass(frozen=True)
class WeightSample:
    age_day: int
    sample_size: int
    average_weight_kg: Decimal


@dataclass(frozen=True)
class DailyLossFacts:
    age_day: int
    deaths: int
    culling: int = 0


def _nonnegative_decimal(value: Decimal, name: str) -> None:
    if not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} must be a finite, non-negative Decimal")


def _nonnegative_count(value: int, name: str) -> None:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def calculate_bird_ledger(
    placed_birds: int, daily_facts: Iterable[DailyBirdFacts]
) -> tuple[DailyBirdBalance, ...]:
    """Rebuild daily closing counts from placement and movement facts.

    Facts must contain no more than one aggregated row per local date. The
    closing count is checked after all same-day movements are combined.
    """
    if isinstance(placed_birds, bool) or placed_birds <= 0:
        raise ValueError("Placed birds must be a positive integer")
    return _calculate_bird_ledger_from(placed_birds, daily_facts)


def calculate_bird_ledger_from_opening(
    opening_birds: int, daily_facts: Iterable[DailyBirdFacts]
) -> tuple[DailyBirdBalance, ...]:
    """Calculate a checked ledger suffix from its known opening bird count."""
    _nonnegative_count(opening_birds, "Opening birds")
    return _calculate_bird_ledger_from(opening_birds, daily_facts)


def recompute_bird_ledger(
    placed_birds: int,
    daily_facts: Iterable[DailyBirdFacts],
    *,
    changed_from: date,
) -> tuple[DailyBirdBalance, ...]:
    """Rebuild the affected suffix after a backdated fact edit.

    The unchanged prefix is derived from the supplied current facts before the
    changed date; every fact on or after that date is then recalculated.
    """
    facts = tuple(daily_facts)
    prefix_facts = tuple(item for item in facts if item.day < changed_from)
    suffix_facts = tuple(item for item in facts if item.day >= changed_from)
    prefix = calculate_bird_ledger(placed_birds, prefix_facts)
    opening = prefix[-1].closing_birds if prefix else placed_birds
    suffix = _calculate_bird_ledger_from(opening, suffix_facts)
    return prefix + suffix


def _calculate_bird_ledger_from(
    opening_birds: int, daily_facts: Iterable[DailyBirdFacts]
) -> tuple[DailyBirdBalance, ...]:
    """Calculate a suffix from a validated count before the first fact."""
    if opening_birds < 0:
        raise ValueError("Opening bird count cannot be negative")
    facts = sorted(daily_facts, key=lambda item: item.day)
    if len({item.day for item in facts}) != len(facts):
        raise ValueError("Daily bird facts must have unique dates")
    balances: list[DailyBirdBalance] = []
    closing = opening_birds
    for item in facts:
        movements = {
            "deaths": item.deaths,
            "culling": item.culling,
            "sold": item.sold,
            "transferred_out": item.transferred_out,
            "transferred_in": item.transferred_in,
        }
        for name, count in movements.items():
            _nonnegative_count(count, name)
        opening = closing
        closing = (
            opening
            - item.deaths
            - item.culling
            - item.sold
            - item.transferred_out
            + item.transferred_in
        )
        if closing < 0:
            raise ValueError(f"Closing bird count cannot be negative on {item.day.isoformat()}")
        balances.append(
            DailyBirdBalance(
                day=item.day,
                opening_birds=opening,
                deaths=item.deaths,
                culling=item.culling,
                sold=item.sold,
                transferred_out=item.transferred_out,
                transferred_in=item.transferred_in,
                closing_birds=closing,
            )
        )
    return tuple(balances)


def total_loss_count(deaths: int, culling: int) -> int:
    """Return total losses while keeping mortality deaths-only."""
    _nonnegative_count(deaths, "deaths")
    _nonnegative_count(culling, "culling")
    return deaths + culling


def interpolate_average_weight_kg(age_day: int, samples: Iterable[WeightSample]) -> Decimal:
    """Linearly interpolate a flock average weight between bracketing samples."""
    if age_day < 0:
        raise ValueError("Bird age cannot be negative")
    ordered = sorted(samples, key=lambda item: item.age_day)
    if not ordered:
        raise ValueError("At least one weight sample is required")
    if len({item.age_day for item in ordered}) != len(ordered):
        raise ValueError("Weight samples must have unique ages")
    for sample in ordered:
        if sample.age_day < 0 or sample.sample_size <= 0:
            raise ValueError("Weight sample age and sample size must be positive")
        _nonnegative_decimal(sample.average_weight_kg, "Average sampled weight")
    if age_day < ordered[0].age_day or age_day > ordered[-1].age_day:
        raise ValueError("Weight interpolation cannot extrapolate beyond sample ages")
    for left, right in zip(ordered, ordered[1:], strict=False):
        if age_day == left.age_day:
            return left.average_weight_kg
        if left.age_day < age_day < right.age_day:
            portion = Decimal(age_day - left.age_day) / Decimal(right.age_day - left.age_day)
            return (
                left.average_weight_kg
                + (right.average_weight_kg - left.average_weight_kg) * portion
            )
    return ordered[-1].average_weight_kg


def estimate_lost_bird_biomass_kg(
    daily_losses: Iterable[DailyLossFacts], samples: Iterable[WeightSample]
) -> Decimal:
    """Estimate dead and culled biomass from age-interpolated flock weights."""
    loss_rows = sorted(daily_losses, key=lambda item: item.age_day)
    if len({item.age_day for item in loss_rows}) != len(loss_rows):
        raise ValueError("Daily loss facts must have unique ages")
    sample_rows = tuple(samples)
    total = ZERO
    for row in loss_rows:
        if row.age_day < 0:
            raise ValueError("Bird age cannot be negative")
        _nonnegative_count(row.deaths, "Deaths")
        _nonnegative_count(row.culling, "Culling")
        total += Decimal(row.deaths + row.culling) * interpolate_average_weight_kg(
            row.age_day, sample_rows
        )
    return total


def calculate_bird_days(ledger: Iterable[DailyBirdBalance]) -> int:
    """Sum birds alive at the start of each included local day."""
    return sum((item.opening_birds for item in ledger), 0)


def calculate_bird_days_for_period(
    placed_birds: int,
    daily_facts: Iterable[DailyBirdFacts],
    placed_on: date,
    start: date,
    end: date,
) -> int:
    """Sum start-of-day flock counts across an inclusive configured date interval."""
    if end < start:
        raise ValueError("Bird-day period end cannot be before its start")
    facts = tuple(daily_facts)
    facts_by_day = {fact.day: fact for fact in facts}
    if len(facts_by_day) != len(facts):
        raise ValueError("Daily bird facts must have unique dates")
    if end < placed_on:
        return 0
    first_day = placed_on
    effective_start = max(start, placed_on)
    expanded: list[DailyBirdFacts] = []
    for index in range((end - first_day).days + 1):
        day = first_day + timedelta(days=index)
        expanded.append(facts_by_day.get(day, DailyBirdFacts(day=day)))
    return sum(
        balance.opening_birds
        for balance in calculate_bird_ledger(placed_birds, expanded)
        if effective_start <= balance.day <= end
    )


def calculate_buyer_outstanding(
    sale_amounts_pkr: Iterable[Decimal], payment_amounts_pkr: Iterable[Decimal]
) -> Decimal:
    """D12 buyer balance: recorded sale amounts minus payments received."""
    sales = tuple(sale_amounts_pkr)
    payments = tuple(payment_amounts_pkr)
    for amount in sales:
        _nonnegative_decimal(amount, "Sale amount")
    for amount in payments:
        _nonnegative_decimal(amount, "Payment amount")
    return sum(sales, ZERO) - sum(payments, ZERO)


def pkr_for_storage(amount_pkr: Decimal) -> Decimal:
    """Round a PKR amount to paisa at persistence, using half-up ties."""
    if not amount_pkr.is_finite():
        raise ValueError("PKR amount must be finite")
    return amount_pkr.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def cumulative_mortality_percent(deaths: int, placed_birds: int) -> Decimal:
    """Cumulative mortality percent: deaths / placement × 100."""
    _nonnegative_count(deaths, "deaths")
    if placed_birds <= 0:
        raise ValueError("Placed birds must be greater than zero")
    return Decimal(deaths) / Decimal(placed_birds) * HUNDRED


def period_mortality_percent(deaths: int, birds_alive_at_period_start: int) -> Decimal:
    """Daily/weekly mortality percent against birds alive at period start."""
    _nonnegative_count(deaths, "deaths")
    if birds_alive_at_period_start <= 0:
        raise ValueError("Birds alive at period start must be greater than zero")
    if deaths > birds_alive_at_period_start:
        raise ValueError("Period deaths cannot exceed birds alive at period start")
    return Decimal(deaths) / Decimal(birds_alive_at_period_start) * HUNDRED


def feed_used_kg(quantity: Decimal, *, unit: str, bag_size_kg: Decimal | None = None) -> Decimal:
    """Convert a feed quantity in kg or bags into kg using configured bag size."""
    _nonnegative_decimal(quantity, "Feed quantity")
    if unit == "kg":
        return quantity
    if unit == "bags":
        if bag_size_kg is None:
            raise ValueError("Configured feed bag size is required for bag quantities")
        _nonnegative_decimal(bag_size_kg, "Feed bag size")
        if bag_size_kg == ZERO:
            raise ValueError("Feed bag size must be greater than zero")
        return quantity * bag_size_kg
    raise ValueError("Feed unit must be 'kg' or 'bags'")


def calculate_feed_metrics(consumption_kg: Iterable[Decimal], bag_size_kg: Decimal) -> FeedMetrics:
    """Sum feed use and express it as configured bag equivalents."""
    _nonnegative_decimal(bag_size_kg, "Feed bag size")
    if bag_size_kg == ZERO:
        raise ValueError("Feed bag size must be greater than zero")
    amounts = tuple(consumption_kg)
    for amount in amounts:
        _nonnegative_decimal(amount, "Feed consumption")
    total = sum(amounts, ZERO)
    return FeedMetrics(total_used_kg=total, bag_equivalent=total / bag_size_kg)


def calculate_feed_stock(
    opening_kg: Decimal,
    purchases_kg: Decimal,
    usage_kg: Decimal,
    returns_to_stock_kg: Decimal,
    adjustments_kg: Decimal,
) -> Decimal:
    """Apply D7 stock equation; adjustment is signed, returns add to stock."""
    for name, value in (
        ("Opening stock", opening_kg),
        ("Purchases", purchases_kg),
        ("Usage", usage_kg),
        ("Returns to stock", returns_to_stock_kg),
    ):
        _nonnegative_decimal(value, name)
    if not adjustments_kg.is_finite():
        raise ValueError("Stock adjustment must be finite")
    stock = opening_kg + purchases_kg - usage_kg + returns_to_stock_kg + adjustments_kg
    if stock < ZERO:
        raise ValueError("Feed stock cannot be negative")
    return stock


def calculate_feed_cover_days(
    stock_kg: Decimal, trailing_seven_day_usage_kg: Decimal
) -> Decimal | None:
    """Return available days of feed from stock and the approved trailing-week usage."""
    _nonnegative_decimal(stock_kg, "Feed stock")
    _nonnegative_decimal(trailing_seven_day_usage_kg, "Trailing seven-day feed use")
    if trailing_seven_day_usage_kg == ZERO:
        return None
    return stock_kg / (trailing_seven_day_usage_kg / Decimal(7))


def calculate_running_fcr(inputs: FlockFcrInputs) -> Decimal:
    """Calculate running raw FCR using sampled live biomass and D6 terms."""
    _validate_fcr_inputs(inputs)
    if inputs.latest_average_weight_kg is None:
        raise ValueError("Latest average weight is required for running FCR")
    if not inputs.latest_average_weight_kg.is_finite() or inputs.latest_average_weight_kg < ZERO:
        raise ValueError("Latest average weight must be finite and non-negative")
    _nonnegative_count(inputs.current_birds_alive, "Current birds alive")
    current_biomass = Decimal(inputs.current_birds_alive) * inputs.latest_average_weight_kg
    net_gain = (
        current_biomass
        + inputs.sold_live_weight_kg
        + inputs.dead_bird_weight_kg
        - inputs.placement_biomass_kg
    )
    return _fcr_ratio(inputs.cumulative_feed_kg, net_gain)


def calculate_final_fcr(inputs: FlockFcrInputs) -> Decimal:
    """Calculate final raw FCR using total sold live weight and D6 terms."""
    _validate_fcr_inputs(inputs)
    net_gain = inputs.sold_live_weight_kg + inputs.dead_bird_weight_kg - inputs.placement_biomass_kg
    return _fcr_ratio(inputs.cumulative_feed_kg, net_gain)


def _validate_fcr_inputs(inputs: FlockFcrInputs) -> None:
    for name, value in (
        ("Cumulative feed", inputs.cumulative_feed_kg),
        ("Sold live weight", inputs.sold_live_weight_kg),
        ("Dead bird weight", inputs.dead_bird_weight_kg),
        ("Placement biomass", inputs.placement_biomass_kg),
    ):
        _nonnegative_decimal(value, name)


def _fcr_ratio(feed_kg: Decimal, net_weight_gain_kg: Decimal) -> Decimal:
    if net_weight_gain_kg <= ZERO:
        raise ValueError("Net live-weight gain must be greater than zero")
    return feed_kg / net_weight_gain_kg


def allocate_farm_cost(
    farm_cost_pkr: Decimal, flock_bird_days: int, total_eligible_bird_days: int
) -> Decimal:
    """Allocate farm costs by an explicitly supplied eligible bird-day total."""
    _nonnegative_decimal(farm_cost_pkr, "Farm cost")
    _nonnegative_count(flock_bird_days, "Flock bird-days")
    if total_eligible_bird_days <= 0:
        raise ValueError("Total eligible bird-days must be greater than zero")
    if flock_bird_days > total_eligible_bird_days:
        raise ValueError("Flock bird-days cannot exceed eligible bird-days")
    return farm_cost_pkr * Decimal(flock_bird_days) / Decimal(total_eligible_bird_days)


def calculate_profit(
    *,
    current_birds_alive: int,
    latest_average_weight_kg: Decimal,
    entered_market_price_pkr_per_kg: Decimal,
    recorded_sales_amount_pkr: Decimal,
    direct_costs_pkr: Decimal,
    allocated_farm_costs_pkr: Decimal,
) -> ProfitResult:
    """Return estimated and actual profit separately; do not round results."""
    _nonnegative_count(current_birds_alive, "Current birds alive")
    for name, value in (
        ("Latest average weight", latest_average_weight_kg),
        ("Entered market price", entered_market_price_pkr_per_kg),
        ("Recorded sales amount", recorded_sales_amount_pkr),
        ("Direct costs", direct_costs_pkr),
        ("Allocated farm costs", allocated_farm_costs_pkr),
    ):
        _nonnegative_decimal(value, name)
    current_biomass = Decimal(current_birds_alive) * latest_average_weight_kg
    estimated_revenue = current_biomass * entered_market_price_pkr_per_kg
    costs = direct_costs_pkr + allocated_farm_costs_pkr
    return ProfitResult(
        estimated_profit_pkr=estimated_revenue - costs,
        actual_profit_pkr=recorded_sales_amount_pkr - costs,
    )
