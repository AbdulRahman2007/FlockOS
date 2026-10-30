from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.farm_access import require_farm_scope, tenant_repository
from app.core.authz import Principal, Role, get_db, require_permission
from app.domain.calculations import (
    DEFAULT_TARGET_WEIGHT_CURVE,
    DailyBirdBalance,
    DailyBirdFacts,
    DailyLossFacts,
    FlockFcrInputs,
    TargetWeightPoint,
    WeightSample as DomainWeightSample,
    calculate_bird_ledger_from_opening,
    calculate_fcr_from_totals,
    calculate_running_fcr,
    cumulative_mortality_percent,
    daily_mortality_above_threshold,
    estimate_lost_bird_biomass_kg,
    fcr_worse_than_target,
    interpolate_average_weight_kg,
    running_fcr_gain_kg,
    target_average_weight_kg,
    daily_mortality_above_threshold,
)
from app.models.daily_records import DailyRecord, WeightSample
from app.models.farm_operations import (
    DirectCost,
    Farm,
    Flock,
    FlockPlacement,
    MarketPrice,
    Sale,
    TenantSettings,
    TenantWeightTarget,
)
from app.models.identity import FarmAssignment
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardFarmFeedStock,
    DashboardMetric,
    DashboardRead,
    DashboardTrendPoint,
    DirectCostCreate,
    DirectCostRead,
    MarketPriceCreate,
    MarketPriceRead,
)
from app.services.audit import record_audit
from app.services.feed_stock import feed_stock_snapshots

router = APIRouter(tags=["dashboard finance"])
Db = Annotated[Session, Depends(get_db)]


def _bird_facts(records: list[DailyRecord], sales: list[Sale]) -> list[DailyBirdFacts]:
    movements: dict[date, dict[str, int]] = defaultdict(
        lambda: {"deaths": 0, "culling": 0, "sold": 0}
    )
    for record in records:
        movements[record.record_date]["deaths"] += record.deaths
        movements[record.record_date]["culling"] += record.culling
    for sale in sales:
        movements[sale.sale_on]["sold"] += sale.birds
    return [DailyBirdFacts(day=day, **facts) for day, facts in sorted(movements.items())]


@router.get("/dashboard", response_model=DashboardRead)
def read_dashboard(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("dashboard:read"))],
) -> DashboardRead:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    tenant_id = principal.tenant_id
    farms_statement = select(Farm).where(Farm.tenant_id == tenant_id)
    if principal.role in (Role.MANAGER, Role.WORKER):
        farms_statement = farms_statement.where(
            Farm.id.in_(
                select(FarmAssignment.farm_id).where(
                    FarmAssignment.tenant_id == tenant_id,
                    FarmAssignment.user_id == principal.user_id,
                )
            )
        )
    farms = list(db.scalars(farms_statement.order_by(Farm.name, Farm.id)).all())
    farm_by_id = {farm.id: farm for farm in farms}
    farm_ids = list(farm_by_id)
    today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    start = today - timedelta(days=29)
    flocks = (
        list(
            db.scalars(
                select(Flock)
                .where(
                    Flock.tenant_id == tenant_id,
                    Flock.farm_id.in_(farm_ids),
                    Flock.status == "active",
                )
                .order_by(Flock.farm_id, Flock.name, Flock.id)
            ).all()
        )
        if farm_ids
        else []
    )
    flock_ids = [flock.id for flock in flocks]

    placements = (
        list(
            db.scalars(
                select(FlockPlacement)
                .where(
                    FlockPlacement.tenant_id == tenant_id, FlockPlacement.flock_id.in_(flock_ids)
                )
                .order_by(FlockPlacement.placed_on, FlockPlacement.id)
            ).all()
        )
        if flock_ids
        else []
    )
    records = (
        list(
            db.scalars(
                select(DailyRecord)
                .where(
                    DailyRecord.tenant_id == tenant_id,
                    DailyRecord.flock_id.in_(flock_ids),
                    DailyRecord.record_date.between(start, today),
                )
                .order_by(DailyRecord.flock_id, DailyRecord.record_date)
            ).all()
        )
        if flock_ids
        else []
    )
    samples = (
        list(
            db.scalars(
                select(WeightSample)
                .where(WeightSample.tenant_id == tenant_id, WeightSample.flock_id.in_(flock_ids))
                .order_by(WeightSample.flock_id, WeightSample.sampled_on.desc())
            ).all()
        )
        if flock_ids
        else []
    )
    sales = (
        list(
            db.scalars(
                select(Sale)
                .where(
                    Sale.tenant_id == tenant_id,
                    Sale.flock_id.in_(flock_ids),
                    Sale.sale_on.between(start, today),
                )
                .order_by(Sale.flock_id, Sale.sale_on)
            ).all()
        )
        if flock_ids
        else []
    )
    history_stats = (
        {
            row.flock_id: row
            for row in db.execute(
                select(
                    DailyRecord.flock_id,
                    func.sum(DailyRecord.deaths).label("deaths"),
                    func.sum(DailyRecord.culling).label("culling"),
                    func.max(DailyRecord.record_date).label("last_record_date"),
                )
                .where(DailyRecord.tenant_id == tenant_id, DailyRecord.flock_id.in_(flock_ids))
                .group_by(DailyRecord.flock_id)
            ).all()
        }
        if flock_ids
        else {}
    )
    cumulative_feed = (
        dict(
            db.execute(
                select(DailyRecord.flock_id, func.sum(DailyRecord.feed_used_kg))
                .where(
                    DailyRecord.tenant_id == tenant_id,
                    DailyRecord.flock_id.in_(flock_ids),
                    DailyRecord.record_date <= today,
                )
                .group_by(DailyRecord.flock_id)
            ).all()
        )
        if flock_ids
        else {}
    )
    sold_weight = (
        dict(
            db.execute(
                select(Sale.flock_id, func.sum(Sale.total_weight_kg))
                .where(
                    Sale.tenant_id == tenant_id,
                    Sale.flock_id.in_(flock_ids),
                    Sale.sale_on <= today,
                )
                .group_by(Sale.flock_id)
            ).all()
        )
        if flock_ids
        else {}
    )
    daily_loss_history = (
        list(
            db.execute(
                select(
                    DailyRecord.flock_id,
                    DailyRecord.record_date,
                    func.sum(DailyRecord.deaths).label("deaths"),
                    func.sum(DailyRecord.culling).label("culling"),
                )
                .where(
                    DailyRecord.tenant_id == tenant_id,
                    DailyRecord.flock_id.in_(flock_ids),
                    DailyRecord.record_date <= today,
                )
                .group_by(DailyRecord.flock_id, DailyRecord.record_date)
                .order_by(DailyRecord.flock_id, DailyRecord.record_date)
            ).all()
        )
        if flock_ids
        else []
    )
    target_rows = list(
        db.scalars(
            select(TenantWeightTarget)
            .where(TenantWeightTarget.tenant_id == tenant_id)
            .order_by(TenantWeightTarget.age_day)
        ).all()
    )
    target_curve = (
        tuple(TargetWeightPoint(item.age_day, item.average_weight_kg) for item in target_rows)
        if target_rows
        else DEFAULT_TARGET_WEIGHT_CURVE
    )
    losses_by_flock: dict[UUID, list[DailyLossFacts]] = defaultdict(list)
    for loss in daily_loss_history:
        placement_date = min(
            (item.placed_on for item in placements if item.flock_id == loss.flock_id),
            default=loss.record_date,
        )
        losses_by_flock[loss.flock_id].append(
            DailyLossFacts(
                age_day=(loss.record_date - placement_date).days,
                deaths=int(loss.deaths),
                culling=int(loss.culling),
            )
        )
    prior_losses = (
        dict(
            db.execute(
                select(
                    DailyRecord.flock_id,
                    func.sum(DailyRecord.deaths + DailyRecord.culling),
                )
                .where(
                    DailyRecord.tenant_id == tenant_id,
                    DailyRecord.flock_id.in_(flock_ids),
                    DailyRecord.record_date < start,
                )
                .group_by(DailyRecord.flock_id)
            ).all()
        )
        if flock_ids
        else {}
    )
    prior_sales = (
        dict(
            db.execute(
                select(Sale.flock_id, func.sum(Sale.birds))
                .where(
                    Sale.tenant_id == tenant_id,
                    Sale.flock_id.in_(flock_ids),
                    Sale.sale_on < start,
                )
                .group_by(Sale.flock_id)
            ).all()
        )
        if flock_ids
        else {}
    )
    settings = db.get(TenantSettings, tenant_id)
    high_daily_mortality = (
        settings.high_daily_mortality_percent if settings else Decimal("0.5")
    )
    early_daily_mortality = (
        settings.early_daily_mortality_percent if settings else Decimal("1.0")
    )
    early_mortality_days = settings.early_mortality_days if settings else 7
    target_fcr = settings.target_fcr if settings else None
    fcr_tolerance = settings.fcr_tolerance_percent if settings else Decimal("5")
    stock_snapshots = feed_stock_snapshots(
        db, tenant_id=tenant_id, farm_ids=farm_ids, as_of=today
    )

    placements_by_flock: dict[UUID, list[FlockPlacement]] = defaultdict(list)
    for placement in placements:
        placements_by_flock[placement.flock_id].append(placement)
    records_by_flock: dict[UUID, list[DailyRecord]] = defaultdict(list)
    for daily_record in records:
        records_by_flock[daily_record.flock_id].append(daily_record)
    samples_by_flock: dict[UUID, list[WeightSample]] = defaultdict(list)
    for weight_sample in samples:
        samples_by_flock[weight_sample.flock_id].append(weight_sample)
    sales_by_flock: dict[UUID, list[Sale]] = defaultdict(list)
    for sale in sales:
        sales_by_flock[sale.flock_id].append(sale)

    current_birds: dict[UUID, int] = {}
    ledger_by_flock: dict[UUID, tuple[DailyBirdBalance, ...]] = {}
    alerts: list[DashboardAlert] = []
    total_birds = 0
    mortality_deaths = 0
    mortality_placed = 0
    total_fcr_feed = Decimal("0")
    total_fcr_gain = Decimal("0")
    fcr_by_flock: dict[UUID, Decimal] = {}
    for flock in flocks:
        flock_placements = placements_by_flock[flock.id]
        placed = sum(item.bird_count for item in flock_placements)
        if placed <= 0:
            continue
        rows = records_by_flock[flock.id]
        daily_facts = _bird_facts(rows, sales_by_flock[flock.id])
        opening = placed - prior_losses.get(flock.id, 0) - prior_sales.get(flock.id, 0)
        ledger = calculate_bird_ledger_from_opening(opening, daily_facts)
        ledger_by_flock[flock.id] = ledger
        alive = ledger[-1].closing_birds if ledger else placed
        current_birds[flock.id] = alive
        stats = history_stats.get(flock.id)
        deaths = int(stats.deaths) if stats else 0
        rate = cumulative_mortality_percent(deaths, placed)
        total_birds += alive
        mortality_deaths += deaths
        mortality_placed += placed
        farm = farm_by_id[flock.farm_id]
        local_today = datetime.now(ZoneInfo(farm.timezone)).date()
        last_record_date = stats.last_record_date if stats else None
        if last_record_date is None or local_today - last_record_date >= timedelta(days=1):
            alerts.append(
                DashboardAlert(
                    kind="missing_daily_record",
                    farm_id=farm.id,
                    flock_id=flock.id,
                    message="daily_record_missing",
                )
            )
        placement_date = min(item.placed_on for item in flock_placements)
        ledger_by_day = {balance.day: balance for balance in ledger}
        high_mortality_found = False
        for daily_record in rows:
            day_balance = ledger_by_day.get(daily_record.record_date)
            if day_balance is None:
                continue
            age_day = (daily_record.record_date - placement_date).days
            if daily_mortality_above_threshold(
                daily_record.deaths,
                day_balance.opening_birds,
                age_day,
                standard_threshold_percent=high_daily_mortality,
                early_threshold_percent=early_daily_mortality,
                early_days=early_mortality_days,
            ):
                high_mortality_found = True
                break
        if high_mortality_found:
            alerts.append(
                DashboardAlert(
                    kind="high_mortality",
                    farm_id=farm.id,
                    flock_id=flock.id,
                    message="daily_mortality_above_threshold",
                )
            )

        placement_weights_complete = all(
            item.average_weight_kg is not None for item in flock_placements
        )
        if placement_weights_complete:
            domain_samples: list[DomainWeightSample] = [
                DomainWeightSample(
                    age_day=(sample.sampled_on - placement_date).days,
                    sample_size=sample.sample_size,
                    average_weight_kg=sample.average_weight_kg,
                )
                for sample in samples_by_flock[flock.id]
                if sample.sampled_on <= today
            ]
            for placement in flock_placements:
                if not any(sample.sampled_on == placement.placed_on for sample in samples_by_flock[flock.id]):
                    domain_samples.append(
                        DomainWeightSample(
                            age_day=(placement.placed_on - placement_date).days,
                            sample_size=1,
                            average_weight_kg=placement.average_weight_kg or Decimal("0"),
                        )
                    )
            placement_biomass = sum(
                (
                    Decimal(item.bird_count) * (item.average_weight_kg or Decimal("0"))
                    for item in flock_placements
                ),
                Decimal("0"),
            )
            try:
                average_weight_today = interpolate_average_weight_kg(
                    (today - placement_date).days, domain_samples
                )
                lost_weight = estimate_lost_bird_biomass_kg(
                    losses_by_flock[flock.id], domain_samples
                )
                fcr_inputs = FlockFcrInputs(
                    cumulative_feed_kg=Decimal(cumulative_feed.get(flock.id) or 0),
                    sold_live_weight_kg=Decimal(sold_weight.get(flock.id) or 0),
                    dead_bird_weight_kg=lost_weight,
                    placement_biomass_kg=placement_biomass,
                    current_birds_alive=alive,
                    latest_average_weight_kg=average_weight_today,
                )
                actual_fcr = calculate_running_fcr(fcr_inputs)
                fcr_by_flock[flock.id] = actual_fcr
                total_fcr_feed += fcr_inputs.cumulative_feed_kg
                total_fcr_gain += running_fcr_gain_kg(fcr_inputs)
                if fcr_worse_than_target(actual_fcr, target_fcr, fcr_tolerance):
                    alerts.append(
                        DashboardAlert(
                            kind="fcr_worse_than_target",
                            farm_id=farm.id,
                            flock_id=flock.id,
                            message="fcr_worse_than_target",
                        )
                    )
            except ValueError:
                # Missing/invalid weights or a non-positive gain make FCR unavailable.
                pass

    avg_mortality = (
        cumulative_mortality_percent(mortality_deaths, mortality_placed)
        if mortality_placed
        else None
    )
    for farm_id, snapshot in stock_snapshots.items():
        if snapshot.status == "low_feed_cover":
            alerts.append(
                DashboardAlert(
                    kind="low_feed_cover",
                    farm_id=farm_id,
                    message="feed_cover_below_threshold",
                )
            )
    available_stocks = [
        item.stock_kg for item in stock_snapshots.values() if item.stock_kg is not None
    ]
    available_cover = [
        item.feed_cover_days
        for item in stock_snapshots.values()
        if item.feed_cover_days is not None
    ]
    dashboard_stock = [
        DashboardFarmFeedStock(
            farm_id=farm_id,
            farm_name=farm_by_id[farm_id].name,
            stock_kg=snapshot.stock_kg,
            feed_cover_days=snapshot.feed_cover_days,
            status=snapshot.status,
        )
        for farm_id, snapshot in stock_snapshots.items()
        if farm_id in farm_by_id
    ]
    fcr_value = (
        calculate_fcr_from_totals(total_fcr_feed, total_fcr_gain)
        if total_fcr_gain > 0
        else None
    )
    metrics: dict[str, DashboardMetric] = {
        "live_birds": DashboardMetric(value=total_birds, status="partial_excludes_transfers"),
        "mortality_percent": DashboardMetric(
            value=avg_mortality,
            status="available" if avg_mortality is not None else "unavailable",
        ),
        "fcr": DashboardMetric(
            value=fcr_value,
            status="available" if fcr_value is not None else "unavailable_missing_weight_facts",
        ),
        "feed_stock_kg": DashboardMetric(
            value=sum(available_stocks, Decimal("0")) if available_stocks else None,
            status=(
                "available"
                if len(available_stocks) == len(stock_snapshots)
                else "partial_missing_opening_stock"
                if available_stocks
                else "unavailable_missing_stock_facts"
            ),
        ),
        "feed_cover_days": DashboardMetric(
            value=min(available_cover) if available_cover else None,
            status=(
                "lowest_farm_cover"
                if len(available_cover) == len(stock_snapshots) and available_cover
                else "partial_farm_cover"
                if available_cover
                else "unavailable_missing_stock_facts"
            ),
        ),
        "estimated_profit_pkr": DashboardMetric(
            value=None, status="unavailable_missing_weight_or_price"
        ),
    }

    if principal.role is not Role.WORKER and farm_ids:
        prices = list(
            db.scalars(
                select(MarketPrice)
                .where(
                    MarketPrice.tenant_id == tenant_id,
                    MarketPrice.farm_id.in_(farm_ids),
                    MarketPrice.effective_on <= today,
                )
                .order_by(
                    MarketPrice.farm_id,
                    MarketPrice.effective_on.desc(),
                    MarketPrice.created_at.desc(),
                )
            ).all()
        )
        costs_by_flock = (
            dict(
                db.execute(
                    select(DirectCost.flock_id, func.coalesce(func.sum(DirectCost.amount_pkr), 0))
                    .where(
                        DirectCost.tenant_id == tenant_id,
                        DirectCost.flock_id.in_(flock_ids),
                        DirectCost.incurred_on <= today,
                    )
                    .group_by(DirectCost.flock_id)
                ).all()
            )
            if flock_ids
            else {}
        )
        latest_price_by_farm: dict[UUID, Decimal] = {}
        for price_row in prices:
            latest_price_by_farm.setdefault(price_row.farm_id, price_row.price_per_kg_pkr)
        weight_by_flock: dict[UUID, Decimal] = {}
        for weight_sample in samples:
            weight_by_flock.setdefault(weight_sample.flock_id, weight_sample.average_weight_kg)
        estimated_profit = Decimal("0")
        complete_profit = bool(flocks)
        for flock in flocks:
            average_weight = weight_by_flock.get(flock.id)
            price = latest_price_by_farm.get(flock.farm_id)
            if average_weight is None or price is None:
                complete_profit = False
                continue
            estimated_profit += Decimal(
                current_birds.get(flock.id, 0)
            ) * average_weight * price - Decimal(costs_by_flock.get(flock.id, 0))
        metrics["estimated_profit_pkr"] = DashboardMetric(
            value=estimated_profit if complete_profit else None,
            status=(
                "partial_excludes_shared_farm_costs"
                if complete_profit
                else "unavailable_missing_weight_or_price"
            ),
        )

    trend_points: list[DashboardTrendPoint] = []
    record_totals: dict[date, list[int | Decimal]] = defaultdict(lambda: [0, 0, Decimal("0")])
    for flock in flocks:
        placement_rows = placements_by_flock[flock.id]
        if not placement_rows:
            continue
        ledger_by_day = {row.day: row for row in ledger_by_flock[flock.id]}
        for daily_record in records_by_flock[flock.id]:
            if daily_record.record_date < start:
                continue
            opening = ledger_by_day[daily_record.record_date].opening_birds
            total = record_totals[daily_record.record_date]
            total[0] = int(total[0]) + daily_record.deaths
            total[1] = int(total[1]) + opening
            total[2] = Decimal(total[2]) + daily_record.feed_used_kg
        for sample in samples_by_flock[flock.id]:
            if start <= sample.sampled_on <= today:
                age_day = (sample.sampled_on - placement_date).days
                trend_points.append(
                    DashboardTrendPoint(
                        day=sample.sampled_on,
                        flock_id=flock.id,
                        flock_name=flock.name,
                        average_weight_kg=sample.average_weight_kg,
                        target_weight_kg=target_average_weight_kg(age_day, target_curve),
                    )
                )
        sample_dates = {item.sampled_on for item in samples_by_flock[flock.id]}
        for target_point in target_curve:
            target_day = placement_date + timedelta(days=target_point.age_day)
            if start <= target_day <= today and target_day not in sample_dates:
                trend_points.append(
                    DashboardTrendPoint(
                        day=target_day,
                        flock_id=flock.id,
                        flock_name=flock.name,
                        target_weight_kg=target_point.average_weight_kg,
                    )
                )
    for trend_day, values in sorted(record_totals.items()):
        trend_deaths = int(values[0])
        trend_opening = int(values[1])
        trend_feed = Decimal(values[2])
        trend_percent = (
            Decimal(trend_deaths) / Decimal(trend_opening) * Decimal(100) if trend_opening else None
        )
        trend_points.append(
            DashboardTrendPoint(
                day=trend_day, mortality_percent=trend_percent, feed_used_kg=trend_feed
            )
        )
    return DashboardRead(
        as_of=today,
        metrics=metrics,
        alerts=alerts,
        trends=sorted(trend_points, key=lambda item: item.day),
        feed_stock_by_farm=dashboard_stock,
        empty=not farms,
    )


@router.post("/farms/{farm_id}/market-prices", response_model=MarketPriceRead, status_code=201)
def add_market_price(
    farm_id: UUID,
    data: MarketPriceCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:write"))],
) -> MarketPriceRead:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    now = datetime.now(UTC)
    row = MarketPrice(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        effective_on=data.effective_on,
        price_per_kg_pkr=data.price_per_kg_pkr,
        created_by=principal.user_id,
        created_at=now,
    )
    db.add(row)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="market_price.create",
        entity_type="market_price",
        entity_id=str(row.id),
        new_value=f"{data.effective_on}:{data.price_per_kg_pkr}",
    )
    db.commit()
    return MarketPriceRead.model_validate(row, from_attributes=True)


@router.post("/farms/{farm_id}/direct-costs", response_model=DirectCostRead, status_code=201)
def add_direct_cost(
    farm_id: UUID,
    data: DirectCostCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:write"))],
) -> DirectCostRead:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    flock = db.scalar(
        select(Flock).where(
            Flock.tenant_id == principal.tenant_id,
            Flock.id == data.flock_id,
            Flock.farm_id == farm_id,
        )
    )
    if flock is None:
        raise HTTPException(404, "Flock not found")
    now = datetime.now(UTC)
    row = DirectCost(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        flock_id=flock.id,
        incurred_on=data.incurred_on,
        amount_pkr=data.amount_pkr,
        description=data.description,
        created_by=principal.user_id,
        updated_by=principal.user_id,
        created_at=now,
        version=1,
    )
    db.add(row)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="direct_cost.create",
        entity_type="direct_cost",
        entity_id=str(row.id),
        new_value=f"{data.incurred_on}:{data.amount_pkr}:{data.description}",
    )
    db.commit()
    return DirectCostRead.model_validate(row, from_attributes=True)
