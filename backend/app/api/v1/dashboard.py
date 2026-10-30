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
    DailyBirdBalance,
    DailyBirdFacts,
    calculate_bird_ledger_from_opening,
    cumulative_mortality_percent,
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
)
from app.models.identity import FarmAssignment
from app.schemas.dashboard import (
    DashboardAlert,
    DashboardMetric,
    DashboardRead,
    DashboardTrendPoint,
    DirectCostCreate,
    DirectCostRead,
    MarketPriceCreate,
    MarketPriceRead,
)
from app.services.audit import record_audit

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
    target_mortality = settings.target_mortality_percent if settings else None

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
        if target_mortality is not None and rate > target_mortality:
            alerts.append(
                DashboardAlert(
                    kind="high_mortality",
                    farm_id=farm.id,
                    flock_id=flock.id,
                    message="mortality_above_target",
                )
            )

    avg_mortality = (
        cumulative_mortality_percent(mortality_deaths, mortality_placed)
        if mortality_placed
        else None
    )
    metrics: dict[str, DashboardMetric] = {
        "live_birds": DashboardMetric(value=total_birds, status="partial_excludes_transfers"),
        "mortality_percent": DashboardMetric(
            value=avg_mortality,
            status="available" if avg_mortality is not None else "unavailable",
        ),
        "fcr": DashboardMetric(value=None, status="unavailable_missing_weight_facts"),
        "feed_cover_days": DashboardMetric(value=None, status="unavailable_missing_stock_facts"),
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
                trend_points.append(
                    DashboardTrendPoint(
                        day=sample.sampled_on,
                        flock_id=flock.id,
                        flock_name=flock.name,
                        average_weight_kg=sample.average_weight_kg,
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
