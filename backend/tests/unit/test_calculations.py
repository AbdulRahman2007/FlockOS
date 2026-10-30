import ast
import json
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.calculations import (
    DailyBirdFacts,
    DailyLossFacts,
    FlockFcrInputs,
    WeightSample,
    allocate_farm_cost,
    calculate_bird_days,
    calculate_bird_days_for_period,
    calculate_bird_ledger,
    calculate_bird_ledger_from_opening,
    calculate_buyer_outstanding,
    calculate_feed_cover_days,
    calculate_feed_metrics,
    calculate_feed_stock,
    calculate_final_fcr,
    calculate_profit,
    calculate_running_fcr,
    cumulative_mortality_percent,
    estimate_lost_bird_biomass_kg,
    feed_used_kg,
    interpolate_average_weight_kg,
    period_mortality_percent,
    pkr_for_storage,
    recompute_bird_ledger,
    total_loss_count,
)


def test_buyer_outstanding_is_sales_less_payments_including_credit_balance() -> None:
    assert calculate_buyer_outstanding(
        [Decimal("120000"), Decimal("80000")],
        [Decimal("100000"), Decimal("25000")],
    ) == Decimal("75000")
    assert calculate_buyer_outstanding([Decimal("100")], [Decimal("125")]) == Decimal("-25")


def test_calculation_module_has_no_framework_or_persistence_imports() -> None:
    module_path = Path(__file__).parents[2] / "app" / "domain" / "calculations.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden = {
        "app.api",
        "app.repositories",
        "fastapi",
        "httpx",
        "pydantic",
        "requests",
        "sqlalchemy",
        "starlette",
    }
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    violations = [
        name
        for name in imports
        if any(name == root or name.startswith(f"{root}.") for root in forbidden)
    ]
    assert violations == []


@pytest.mark.parametrize(
    ("placed", "facts", "expected"),
    [
        (5000, [DailyBirdFacts(date(2026, 1, 1), 30, 5, 100, 20, 10)], 4855),
        (10, [DailyBirdFacts(date(2026, 1, 2), transferred_in=4)], 14),
        (12, [], None),
    ],
)
def test_bird_ledger_table(placed: int, facts: list[DailyBirdFacts], expected: int | None) -> None:
    ledger = calculate_bird_ledger(placed, facts)
    if expected is None:
        assert ledger == ()
    else:
        assert ledger[-1].closing_birds == expected


def test_bird_ledger_suffix_accepts_zero_opening_after_prior_losses() -> None:
    ledger = calculate_bird_ledger_from_opening(
        0, [DailyBirdFacts(date(2026, 1, 1)), DailyBirdFacts(date(2026, 1, 2), transferred_in=3)]
    )
    assert [row.closing_birds for row in ledger] == [0, 3]


def test_bird_ledger_sorts_dates_and_rejects_overdraw_and_duplicate_dates() -> None:
    facts = [
        DailyBirdFacts(date(2026, 1, 2), deaths=2),
        DailyBirdFacts(date(2026, 1, 1), deaths=3),
    ]
    ledger = calculate_bird_ledger(10, facts)
    assert [entry.closing_birds for entry in ledger] == [7, 5]
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_bird_ledger(2, [DailyBirdFacts(date(2026, 1, 1), deaths=3)])
    with pytest.raises(ValueError, match="unique dates"):
        calculate_bird_ledger(
            10,
            [
                DailyBirdFacts(date(2026, 1, 1)),
                DailyBirdFacts(date(2026, 1, 1), deaths=1),
            ],
        )
    with pytest.raises(ValueError, match="positive integer"):
        calculate_bird_ledger(0, [])


def test_candidate_golden_fixture_bird_counts_match_spreadsheet() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "golden_5000_broiler_candidate.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "Synthetic golden case" in fixture["_note"]
    inputs = fixture["inputs"]
    sales_by_day: dict[int, int] = {}
    for sale in fixture["sales"]:
        sales_by_day[sale["day"]] = sales_by_day.get(sale["day"], 0) + sale["birds"]
    placement_date = date.fromisoformat(inputs["placement_date"])
    facts = [
        DailyBirdFacts(
            day=placement_date + timedelta(days=row["day"]),
            deaths=row["mortality"],
            culling=row["culling"],
            sold=sales_by_day.get(row["day"], 0),
        )
        for row in fixture["daily"]
    ]
    ledger = calculate_bird_ledger(inputs["birds_placed"], facts)
    expected = fixture["expected"]
    assert expected["G-01"]["value"] == str(inputs["birds_placed"])
    assert sum(row.deaths for row in facts) == int(expected["G-02"]["value"])
    assert sum(row.culling for row in facts) == int(expected["G-03"]["value"])
    assert sum(row.sold for row in facts) == int(expected["G-04"]["value"])
    assert ledger[-1].closing_birds == int(expected["G-05"]["value"])


def test_candidate_golden_case_matches_outputs_under_documented_assumptions() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "golden_5000_broiler_candidate.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    inputs = fixture["inputs"]
    rows = fixture["daily"]
    samples = [
        WeightSample(
            age_day=sample["day"],
            sample_size=inputs["weight_sample_size"],
            average_weight_kg=Decimal(sample["avg_weight_kg"]),
        )
        for sample in inputs["weight_samples"]
    ]
    sales_by_day: dict[int, list[dict[str, int]]] = {}
    for sale in fixture["sales"]:
        sales_by_day.setdefault(sale["day"], []).append(sale)
    facts = [
        DailyBirdFacts(
            day=date.fromisoformat(inputs["placement_date"]) + timedelta(days=row["day"]),
            deaths=row["mortality"],
            culling=row["culling"],
            sold=sum(sale["birds"] for sale in sales_by_day.get(row["day"], [])),
        )
        for row in rows
    ]
    ledger = calculate_bird_ledger(inputs["birds_placed"], facts)
    daily_losses = [DailyLossFacts(row["day"], row["mortality"], row["culling"]) for row in rows]
    feed_movements: dict[int, dict[str, Decimal]] = {}
    for movement in fixture["feed_movements"]:
        daily = feed_movements.setdefault(
            movement["day"],
            {"purchases": Decimal("0"), "returns": Decimal("0"), "adjustments": Decimal("0")},
        )
        if movement["type"] == "Purchase":
            daily["purchases"] += feed_used_kg(
                Decimal(movement["bags"]),
                unit="bags",
                bag_size_kg=Decimal(inputs["bag_size_kg"]),
            )
        elif movement["type"] == "Return":
            daily["returns"] += abs(Decimal(movement["signed_kg"]))
        else:
            daily["adjustments"] += Decimal(movement["signed_kg"])

    stock = Decimal(inputs["opening_feed_stock_kg"])
    daily_stocks: dict[int, Decimal] = {}
    minimum_stock: Decimal | None = None
    cumulative_feed: dict[int, Decimal] = {}
    total_feed = Decimal("0")
    feed_price_per_kg = Decimal(inputs["feed_price_per_bag_pkr"]) / Decimal(inputs["bag_size_kg"])
    for row in rows:
        movement = feed_movements.get(
            row["day"],
            {"purchases": Decimal("0"), "returns": Decimal("0"), "adjustments": Decimal("0")},
        )
        used = Decimal(row["feed_used_kg"])
        stock = calculate_feed_stock(
            stock,
            movement["purchases"],
            used,
            movement["returns"],
            movement["adjustments"],
        )
        daily_stocks[row["day"]] = stock
        minimum_stock = stock if minimum_stock is None else min(minimum_stock, stock)
        total_feed += used
        cumulative_feed[row["day"]] = total_feed

    total_deaths = sum(row["mortality"] for row in rows)
    total_culls = sum(row["culling"] for row in rows)
    total_sold_birds = sum(sale["birds"] for sale in fixture["sales"])
    total_sold_weight = sum(
        (Decimal(sale["total_weight_kg"]) for sale in fixture["sales"]), Decimal("0")
    )
    sale_revenue = sum(
        (
            Decimal(sale["total_weight_kg"]) * Decimal(sale["rate_per_kg_pkr"])
            for sale in fixture["sales"]
        ),
        Decimal("0"),
    )
    payments = sum((Decimal(sale["paid_pkr"]) for sale in fixture["sales"]), Decimal("0"))
    lost_biomass = estimate_lost_bird_biomass_kg(daily_losses, samples)
    placement_biomass = Decimal(inputs["birds_placed"]) * Decimal(inputs["placement_weight_kg"])
    bird_days = calculate_bird_days(ledger)
    farm_share = Decimal(bird_days) / Decimal(bird_days + inputs["other_flocks_bird_days"])
    farm_allocation = Decimal(inputs["farm_expense_pool_pkr"]) * farm_share
    flock_expenses = sum(
        (Decimal(item["amount_pkr"]) for item in fixture["expenses"]), Decimal("0")
    )
    chick_cost = Decimal(inputs["birds_placed"]) * Decimal(inputs["chick_price_pkr"])
    feed_cost = total_feed * feed_price_per_kg
    total_costs = chick_cost + feed_cost + flock_expenses + farm_allocation
    final_gain = total_sold_weight + lost_biomass - placement_biomass
    actual_profit = sale_revenue - total_costs

    def matches_displayed(actual: Decimal, expected_text: str) -> bool:
        expected = Decimal(expected_text)
        quantum = Decimal(1).scaleb(expected.as_tuple().exponent)
        return actual.quantize(quantum, rounding=ROUND_HALF_EVEN) == expected

    expected = fixture["expected"]
    output_values = {
        "G-01": Decimal(inputs["birds_placed"]),
        "G-02": Decimal(total_deaths),
        "G-03": Decimal(total_culls),
        "G-04": Decimal(total_sold_birds),
        "G-05": Decimal(ledger[-1].closing_birds),
        "G-06": cumulative_mortality_percent(total_deaths, inputs["birds_placed"]),
        "G-07": Decimal(total_deaths + total_culls) / Decimal(inputs["birds_placed"]) * 100,
        "G-08": period_mortality_percent(rows[0]["mortality"], ledger[0].opening_birds),
        "G-09": period_mortality_percent(rows[-1]["mortality"], ledger[-1].opening_birds),
        "G-10": total_feed,
        # The source's negative Return sign is normalized to +100 kg per owner instruction.
        "G-11": daily_stocks[35],
        "G-12": minimum_stock,
        "G-13": total_sold_weight,
        "G-14": lost_biomass,
        "G-15": placement_biomass,
        "G-16": final_gain,
        "G-17": total_feed / final_gain,
        "G-18": total_feed / (total_sold_weight - placement_biomass),
        "G-19": sale_revenue,
        "G-20": payments,
        "G-21": sale_revenue - payments,
        "G-22": chick_cost,
        "G-23": feed_cost,
        "G-24": flock_expenses,
        "G-25": Decimal(bird_days),
        "G-26": farm_share,
        "G-27": farm_allocation,
        "G-28": total_costs,
        "G-29": actual_profit,
        "G-30": actual_profit / Decimal(inputs["birds_placed"]),
        "G-31": actual_profit / total_sold_weight,
    }
    for key, actual in output_values.items():
        source_expected = expected[key]["value"]
        if key in {"G-06", "G-07", "G-08", "G-09"}:
            source_expected = str(Decimal(source_expected) * 100)
        if key == "G-09":
            # Draft fractions are rounded; compare the stable displayed percent digits.
            source_expected = str(Decimal(source_expected).quantize(Decimal("0.000000000000001")))
        if key == "G-16":
            # Recompute from G-13 + G-14 - G-15 under A1; source G-16 differs by 0.00000000001.
            source_expected = "9647.33571428571"
        if key == "G-11":
            # The source spreadsheet subtracted a signed -100 kg. D7 says returns add.
            source_expected = str(Decimal(source_expected) + 200)
        if key == "G-31":
            # Recompute per-kg profit from the corrected D8 allocated-cost result.
            source_expected = "8.721262832885548711525898624"
        if key == "G-29":
            # Corrected to use the unrounded D8 bird-day allocation.
            source_expected = "84910.214940973702255416149"
        assert matches_displayed(actual, source_expected), key

    checkpoint_outputs = fixture["checkpoints"]
    for checkpoint in checkpoint_outputs:
        day = int(checkpoint["day"])
        balance = ledger[day - 1]
        average_weight = interpolate_average_weight_kg(day, samples)
        sold_weight_to_date = sum(
            (Decimal(sale["total_weight_kg"]) for sale in fixture["sales"] if sale["day"] <= day),
            Decimal("0"),
        )
        lost_to_date = estimate_lost_bird_biomass_kg(
            (item for item in daily_losses if item.age_day <= day), samples
        )
        gain = (
            Decimal(balance.closing_birds) * average_weight
            + sold_weight_to_date
            + lost_to_date
            - placement_biomass
        )
        values = {
            "closing_birds": Decimal(balance.closing_birds),
            "cum_mortality_pct": cumulative_mortality_percent(
                sum(row["mortality"] for row in rows[:day]), inputs["birds_placed"]
            ),
            "daily_mortality_pct": period_mortality_percent(
                rows[day - 1]["mortality"], balance.opening_birds
            ),
            "avg_weight_kg": average_weight,
            "live_weight_kg": Decimal(balance.closing_birds) * average_weight,
            "cum_sold_weight_kg": sold_weight_to_date,
            "cum_dead_weight_kg": lost_to_date,
            "placement_weight_kg": placement_biomass,
            "weight_gain_kg": gain,
            "cum_feed_kg": cumulative_feed[day],
            "cum_fcr": cumulative_feed[day] / gain,
            "closing_feed_stock_kg": daily_stocks[day],
        }
        for key, actual in values.items():
            expected_value = checkpoint[key]
            if key in {"cum_mortality_pct", "daily_mortality_pct"}:
                expected_value = str(
                    (Decimal(expected_value) * 100).quantize(Decimal("0.000000000000001"))
                )
            if key == "weight_gain_kg" and day == 35:
                expected_value = "9647.33571428571"
            if key == "closing_feed_stock_kg" and day >= 31:
                expected_value = str(Decimal(expected_value) + 200)
            assert matches_displayed(actual, expected_value), f"checkpoint {day} {key}"

    checkpoint_day = inputs["checkpoint_day"]
    checkpoint_balance = ledger[checkpoint_day - 1]
    checkpoint_bird_days = calculate_bird_days(ledger[:checkpoint_day])
    checkpoint_share_cost = allocate_farm_cost(
        Decimal(inputs["farm_expense_pool_pkr"]),
        checkpoint_bird_days,
        checkpoint_bird_days + inputs["other_flocks_bird_days"],
    )
    checkpoint_feed_cost = cumulative_feed[checkpoint_day] * feed_price_per_kg
    checkpoint_flock_expenses = sum(
        (
            Decimal(item["amount_pkr"])
            for item in fixture["expenses"]
            if item["day"] <= checkpoint_day
        ),
        Decimal("0"),
    )
    estimated = calculate_profit(
        current_birds_alive=checkpoint_balance.closing_birds,
        latest_average_weight_kg=interpolate_average_weight_kg(checkpoint_day, samples),
        entered_market_price_pkr_per_kg=Decimal(inputs["market_price_per_kg_pkr"]),
        recorded_sales_amount_pkr=sale_revenue,
        direct_costs_pkr=chick_cost + checkpoint_feed_cost + checkpoint_flock_expenses,
        allocated_farm_costs_pkr=checkpoint_share_cost,
    )
    # The revised value includes D8's checkpoint bird-day farm-cost allocation.
    assert matches_displayed(estimated.estimated_profit_pkr, "-1252.969690342713191661164")


def test_weight_interpolation_and_lost_biomass_assumption() -> None:
    samples = [
        WeightSample(0, 50, Decimal("0.04")),
        WeightSample(7, 50, Decimal("0.185")),
        WeightSample(14, 50, Decimal("0.465")),
    ]
    assert interpolate_average_weight_kg(7, samples) == Decimal("0.185")
    expected_interpolated = Decimal("0.04") + (Decimal("0.185") - Decimal("0.04")) / Decimal(7)
    assert interpolate_average_weight_kg(1, samples).quantize(
        Decimal("1e-27")
    ) == expected_interpolated.quantize(Decimal("1e-27"))
    losses = [DailyLossFacts(5, deaths=7, culling=3)]
    assert estimate_lost_bird_biomass_kg(losses, samples) == Decimal(10) * (
        Decimal("0.04") + (Decimal("0.185") - Decimal("0.04")) * Decimal(5) / Decimal(7)
    )
    assert (
        calculate_bird_days(
            calculate_bird_ledger(
                5000,
                [DailyBirdFacts(date(2026, 1, 1), deaths=10), DailyBirdFacts(date(2026, 1, 2))],
            )
        )
        == 9990
    )
    with pytest.raises(ValueError, match="cannot extrapolate"):
        interpolate_average_weight_kg(15, samples)
    with pytest.raises(ValueError, match="unique ages"):
        interpolate_average_weight_kg(1, [samples[0], samples[0]])


def test_pkr_storage_rounds_half_up_only_at_storage_boundary() -> None:
    assert pkr_for_storage(Decimal("1.004")) == Decimal("1.00")
    assert pkr_for_storage(Decimal("1.005")) == Decimal("1.01")
    assert pkr_for_storage(Decimal("-1.005")) == Decimal("-1.01")


@pytest.mark.parametrize(("deaths", "culling", "expected"), [(40, 6, 46), (0, 0, 0), (1, 0, 1)])
def test_total_loss_keeps_deaths_and_culling_separate(
    deaths: int, culling: int, expected: int
) -> None:
    assert total_loss_count(deaths, culling) == expected


def test_mortality_percent_examples_and_invalid_denominators() -> None:
    assert cumulative_mortality_percent(40, 5000) == Decimal("0.8")
    assert period_mortality_percent(14, 4900) == Decimal(14) / Decimal(4900) * 100
    with pytest.raises(ValueError, match="greater than zero"):
        cumulative_mortality_percent(0, 0)
    with pytest.raises(ValueError, match="greater than zero"):
        period_mortality_percent(0, 0)
    with pytest.raises(ValueError, match="cannot exceed"):
        period_mortality_percent(4, 3)
    with pytest.raises(ValueError, match="non-negative integer"):
        total_loss_count(-1, 0)


def test_feed_conversions_metrics_and_stock_examples() -> None:
    assert feed_used_kg(Decimal("20"), unit="bags", bag_size_kg=Decimal("50")) == Decimal("1000")
    assert feed_used_kg(Decimal("2.5"), unit="kg") == Decimal("2.5")
    metrics = calculate_feed_metrics([Decimal("350"), Decimal("350")], Decimal("50"))
    assert metrics.total_used_kg == Decimal("700")
    assert metrics.bag_equivalent == Decimal("14")
    assert calculate_feed_stock(
        Decimal("1000"), Decimal("1000"), Decimal("700"), Decimal("25"), Decimal("10")
    ) == Decimal("1335")


def test_feed_cover_uses_trailing_seven_day_usage() -> None:
    assert calculate_feed_cover_days(Decimal("700"), Decimal("700")) == Decimal("7")
    assert calculate_feed_cover_days(Decimal("700"), Decimal("0")) is None


@pytest.mark.parametrize(
    "call",
    [
        lambda: feed_used_kg(Decimal("1"), unit="bags"),
        lambda: feed_used_kg(Decimal("1"), unit="tonnes"),
        lambda: feed_used_kg(Decimal("-1"), unit="kg"),
        lambda: feed_used_kg(Decimal("1"), unit="bags", bag_size_kg=Decimal("0")),
        lambda: calculate_feed_metrics([Decimal("-1")], Decimal("50")),
        lambda: calculate_feed_metrics([], Decimal("0")),
        lambda: calculate_feed_stock(
            Decimal("0"), Decimal("0"), Decimal("1"), Decimal("0"), Decimal("0")
        ),
        lambda: calculate_feed_stock(
            Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("-1")
        ),
    ],
)
def test_feed_functions_reject_invalid_inputs(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_fcr_examples_and_invalid_net_gain() -> None:
    running = FlockFcrInputs(
        cumulative_feed_kg=Decimal("12000"),
        sold_live_weight_kg=Decimal("500"),
        dead_bird_weight_kg=Decimal("120"),
        placement_biomass_kg=Decimal("500"),
        current_birds_alive=4000,
        latest_average_weight_kg=Decimal("1.2"),
    )
    assert calculate_running_fcr(running) == Decimal("12000") / Decimal("4920")
    final = FlockFcrInputs(
        cumulative_feed_kg=Decimal("14000"),
        sold_live_weight_kg=Decimal("6200"),
        dead_bird_weight_kg=Decimal("150"),
        placement_biomass_kg=Decimal("500"),
    )
    assert calculate_final_fcr(final) == Decimal("14000") / Decimal("5850")
    with pytest.raises(ValueError, match="required"):
        calculate_running_fcr(final)
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_final_fcr(FlockFcrInputs(Decimal("0"), Decimal("1"), Decimal("0"), Decimal("1")))
    with pytest.raises(ValueError, match="non-negative"):
        calculate_final_fcr(FlockFcrInputs(Decimal("-1"), Decimal("2"), Decimal("0"), Decimal("1")))


def test_bird_day_allocation_and_profit_examples() -> None:
    assert allocate_farm_cost(Decimal("15000"), 1000, 1500) == Decimal("10000")
    result = calculate_profit(
        current_birds_alive=1000,
        latest_average_weight_kg=Decimal("1"),
        entered_market_price_pkr_per_kg=Decimal("300"),
        recorded_sales_amount_pkr=Decimal("280000"),
        direct_costs_pkr=Decimal("180000"),
        allocated_farm_costs_pkr=Decimal("10000"),
    )
    assert result.estimated_profit_pkr == Decimal("110000")
    assert result.actual_profit_pkr == Decimal("90000")


def test_configured_bird_day_period_carries_daily_movements_through_empty_days() -> None:
    ledger_days = calculate_bird_days_for_period(
        100,
        [
            DailyBirdFacts(day=date(2026, 1, 2), deaths=10),
            DailyBirdFacts(day=date(2026, 1, 4), sold=20),
        ],
        date(2026, 1, 1),
        date(2026, 1, 1),
        date(2026, 1, 5),
    )
    assert ledger_days == 100 + 100 + 90 + 90 + 70


@pytest.mark.parametrize(
    ("placed_on", "start", "end", "facts", "expected"),
    [
        (date(2026, 1, 3), date(2026, 1, 1), date(2026, 1, 2), [], 0),
        (date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 1), [], 100),
    ],
)
def test_configured_bird_days_period_boundaries(placed_on, start, end, facts, expected) -> None:
    assert calculate_bird_days_for_period(100, facts, placed_on, start, end) == expected


def test_configured_bird_days_period_rejects_invalid_interval_and_duplicate_events() -> None:
    with pytest.raises(ValueError, match="before its start"):
        calculate_bird_days_for_period(
            100, [], date(2026, 1, 1), date(2026, 1, 3), date(2026, 1, 2)
        )
    duplicate = DailyBirdFacts(day=date(2026, 1, 1))
    with pytest.raises(ValueError, match="unique dates"):
        calculate_bird_days_for_period(
            100,
            [duplicate, duplicate],
            date(2026, 1, 1),
            date(2026, 1, 1),
            date(2026, 1, 1),
        )


@pytest.mark.parametrize(
    "call",
    [
        lambda: allocate_farm_cost(Decimal("1"), 0, 0),
        lambda: allocate_farm_cost(Decimal("1"), 2, 1),
        lambda: allocate_farm_cost(Decimal("-1"), 1, 1),
        lambda: calculate_profit(
            current_birds_alive=-1,
            latest_average_weight_kg=Decimal("1"),
            entered_market_price_pkr_per_kg=Decimal("1"),
            recorded_sales_amount_pkr=Decimal("0"),
            direct_costs_pkr=Decimal("0"),
            allocated_farm_costs_pkr=Decimal("0"),
        ),
    ],
)
def test_profit_functions_reject_invalid_inputs(call) -> None:
    with pytest.raises(ValueError):
        call()


@given(
    placed=st.integers(min_value=1, max_value=100_000),
    losses=st.lists(st.integers(min_value=0, max_value=1_000), min_size=0, max_size=35),
    incoming=st.lists(st.integers(min_value=0, max_value=1_000), min_size=0, max_size=35),
)
def test_bird_counts_never_negative_and_always_reconcile(
    placed: int, losses: list[int], incoming: list[int]
) -> None:
    size = max(len(losses), len(incoming))
    facts = []
    alive = placed
    for index in range(size):
        deaths = min(losses[index], alive) if index < len(losses) else 0
        transferred_in = incoming[index] if index < len(incoming) else 0
        facts.append(
            DailyBirdFacts(
                date(2026, 1, 1) + timedelta(days=index),
                deaths=deaths,
                transferred_in=transferred_in,
            )
        )
        alive = alive - deaths + transferred_in
    ledger = calculate_bird_ledger(placed, facts)
    previous = placed
    for item, balance in zip(facts, ledger, strict=True):
        assert balance.opening_birds == previous
        assert balance.closing_birds == previous - item.deaths + item.transferred_in
        assert balance.closing_birds >= 0
        previous = balance.closing_birds


@given(
    original=st.lists(st.integers(min_value=0, max_value=1000), min_size=5, max_size=5),
    replacement=st.integers(min_value=0, max_value=1000),
)
def test_backdated_edit_recompute_matches_fresh_compute(
    original: list[int], replacement: int
) -> None:
    first_day = date(2026, 1, 1)
    edited = [
        DailyBirdFacts(
            first_day + timedelta(days=index), deaths=(replacement if index == 2 else count)
        )
        for index, count in enumerate(original)
    ]
    assert recompute_bird_ledger(10_000, edited, changed_from=first_day + timedelta(days=2)) == (
        calculate_bird_ledger(10_000, edited)
    )
