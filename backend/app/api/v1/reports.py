from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.api.v1.finance import flock_profit
from app.core.authz import Principal, Role, get_db, require_permission
from app.domain.calculations import period_mortality_percent
from app.models.daily_records import DailyRecord, FeedPurchase, WeightSample
from app.models.farm_operations import (
    Buyer,
    Expense,
    Farm,
    Flock,
    FlockPlacement,
    Sale,
    SalePayment,
)
from app.models.identity import FarmAssignment

router = APIRouter(prefix="/reports", tags=["reports"])
Db = Annotated[Session, Depends(get_db)]
ReportType = Literal["flocks", "mortality", "feed", "weight", "financial", "profitability"]


def _scope(principal: Principal, farm_id: UUID | None, flock_id: UUID | None) -> list[Any]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    conditions: list[Any] = [Flock.tenant_id == principal.tenant_id]
    if farm_id is not None:
        conditions.append(Flock.farm_id == farm_id)
    if flock_id is not None:
        conditions.append(Flock.id == flock_id)
    if principal.role is Role.MANAGER:
        assigned = select(FarmAssignment.farm_id).where(
            FarmAssignment.tenant_id == principal.tenant_id,
            FarmAssignment.user_id == principal.user_id,
        )
        conditions.append(Flock.farm_id.in_(assigned))
    return conditions


def _report_page(
    report_type: ReportType,
    db: Session,
    principal: Principal,
    start_date: date,
    end_date: date,
    farm_id: UUID | None,
    flock_id: UUID | None,
    limit: int,
    offset: int,
    include_metadata: bool = True,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    scope = _scope(principal, farm_id, flock_id)
    tenant_id = principal.tenant_id

    if report_type == "flocks":
        placed_in_range = select(FlockPlacement.flock_id).where(
            FlockPlacement.tenant_id == tenant_id,
            FlockPlacement.placed_on.between(start_date, end_date),
        )
        placement_totals = (
            select(
                FlockPlacement.flock_id, func.sum(FlockPlacement.bird_count).label("placed_birds")
            )
            .where(
                FlockPlacement.tenant_id == tenant_id,
                FlockPlacement.placed_on <= end_date,
            )
            .group_by(FlockPlacement.flock_id)
            .subquery()
        )
        loss_totals = (
            select(
                DailyRecord.flock_id,
                func.sum(DailyRecord.deaths + DailyRecord.culling).label("losses"),
            )
            .where(
                DailyRecord.tenant_id == tenant_id,
                DailyRecord.record_date <= end_date,
            )
            .group_by(DailyRecord.flock_id)
            .subquery()
        )
        sales_totals = (
            select(Sale.flock_id, func.sum(Sale.birds).label("sold_birds"))
            .where(Sale.tenant_id == tenant_id, Sale.sale_on <= end_date)
            .group_by(Sale.flock_id)
            .subquery()
        )
        flock_report_statement = (
            select(
                Flock.id.label("flock_id"),
                Flock.name.label("flock"),
                Farm.name.label("farm"),
                Flock.status.label("status"),
                func.coalesce(placement_totals.c.placed_birds, 0).label("placed_birds"),
                func.coalesce(loss_totals.c.losses, 0).label("losses"),
                func.coalesce(sales_totals.c.sold_birds, 0).label("sold_birds"),
                (
                    func.coalesce(placement_totals.c.placed_birds, 0)
                    - func.coalesce(loss_totals.c.losses, 0)
                    - func.coalesce(sales_totals.c.sold_birds, 0)
                ).label("live_birds"),
            )
            .join(Farm, (Farm.tenant_id == Flock.tenant_id) & (Farm.id == Flock.farm_id))
            .outerjoin(placement_totals, placement_totals.c.flock_id == Flock.id)
            .outerjoin(loss_totals, loss_totals.c.flock_id == Flock.id)
            .outerjoin(sales_totals, sales_totals.c.flock_id == Flock.id)
            .where(*scope)
            .where(Flock.status == "active")
            .where(Flock.id.in_(placed_in_range))
            .order_by(Farm.name, Flock.name, Flock.id)
        )
        count = (
            db.scalar(select(func.count()).select_from(flock_report_statement.subquery())) or 0
            if include_metadata
            else 0
        )
        flock_rows = [
            dict(row._mapping)
            for row in db.execute(flock_report_statement.limit(limit).offset(offset))
        ]
        if not include_metadata:
            return flock_rows, count, {}
        placed = (
            db.scalar(
                select(func.coalesce(func.sum(placement_totals.c.placed_birds), 0))
                .select_from(Flock)
                .outerjoin(placement_totals, placement_totals.c.flock_id == Flock.id)
                .where(*scope, Flock.status == "active", Flock.id.in_(placed_in_range))
            )
            or 0
        )
        live = (
            db.scalar(
                select(
                    func.coalesce(func.sum(placement_totals.c.placed_birds), 0)
                    - func.coalesce(func.sum(loss_totals.c.losses), 0)
                    - func.coalesce(func.sum(sales_totals.c.sold_birds), 0)
                )
                .select_from(Flock)
                .outerjoin(placement_totals, placement_totals.c.flock_id == Flock.id)
                .outerjoin(loss_totals, loss_totals.c.flock_id == Flock.id)
                .outerjoin(sales_totals, sales_totals.c.flock_id == Flock.id)
                .where(*scope, Flock.status == "active", Flock.id.in_(placed_in_range))
            )
            or 0
        )
        return flock_rows, count, {"placed_birds": int(placed), "live_birds": int(live)}

    if report_type == "mortality":
        placements_at_start = (
            select(
                FlockPlacement.flock_id,
                func.sum(FlockPlacement.bird_count).label("placed"),
            )
            .where(
                FlockPlacement.tenant_id == tenant_id,
                FlockPlacement.placed_on <= start_date,
            )
            .group_by(FlockPlacement.flock_id)
            .subquery()
        )
        losses_before_start = (
            select(
                DailyRecord.flock_id,
                func.sum(DailyRecord.deaths + DailyRecord.culling).label("lost"),
            )
            .where(
                DailyRecord.tenant_id == tenant_id,
                DailyRecord.record_date < start_date,
            )
            .group_by(DailyRecord.flock_id)
            .subquery()
        )
        sales_before_start = (
            select(Sale.flock_id, func.sum(Sale.birds).label("sold"))
            .where(Sale.tenant_id == tenant_id, Sale.sale_on < start_date)
            .group_by(Sale.flock_id)
            .subquery()
        )
        period_losses = (
            select(
                DailyRecord.flock_id,
                func.sum(DailyRecord.deaths).label("deaths"),
                func.sum(DailyRecord.culling).label("culling"),
            )
            .where(
                DailyRecord.tenant_id == tenant_id,
                DailyRecord.record_date.between(start_date, end_date),
            )
            .group_by(DailyRecord.flock_id)
            .subquery()
        )
        mortality_statement = (
            select(
                Flock.id.label("flock_id"),
                Flock.name.label("flock"),
                (
                    func.coalesce(placements_at_start.c.placed, 0)
                    - func.coalesce(losses_before_start.c.lost, 0)
                    - func.coalesce(sales_before_start.c.sold, 0)
                ).label("opening_birds"),
                func.coalesce(period_losses.c.deaths, 0).label("deaths"),
                func.coalesce(period_losses.c.culling, 0).label("culling"),
            )
            .outerjoin(placements_at_start, placements_at_start.c.flock_id == Flock.id)
            .outerjoin(losses_before_start, losses_before_start.c.flock_id == Flock.id)
            .outerjoin(sales_before_start, sales_before_start.c.flock_id == Flock.id)
            .outerjoin(period_losses, period_losses.c.flock_id == Flock.id)
            .where(*scope)
            .order_by(Flock.name, Flock.id)
        )
        count = (
            db.scalar(select(func.count()).select_from(mortality_statement.subquery())) or 0
            if include_metadata
            else 0
        )
        selected_rows = db.execute(mortality_statement.limit(limit).offset(offset)).all()
        mortality_rows = [
            {
                **dict(row._mapping),
                "period_start": start_date,
                "period_end": end_date,
                "mortality_percent": (
                    period_mortality_percent(row.deaths, row.opening_birds)
                    if row.opening_birds > 0 and row.deaths <= row.opening_birds
                    else None
                ),
                "status": (
                    "available"
                    if row.opening_birds > 0 and row.deaths <= row.opening_birds
                    else "opening_birds_unavailable"
                ),
            }
            for row in selected_rows
        ]
        if not include_metadata:
            return mortality_rows, count, {}
        deaths_total = (
            db.scalar(
                select(func.coalesce(func.sum(period_losses.c.deaths), 0))
                .select_from(Flock)
                .outerjoin(period_losses, period_losses.c.flock_id == Flock.id)
                .where(*scope)
            )
            or 0
        )
        culling_total = (
            db.scalar(
                select(func.coalesce(func.sum(period_losses.c.culling), 0))
                .select_from(Flock)
                .outerjoin(period_losses, period_losses.c.flock_id == Flock.id)
                .where(*scope)
            )
            or 0
        )
        return mortality_rows, count, {"deaths": int(deaths_total), "culling": int(culling_total)}

    if report_type in ("feed", "weight"):
        model = DailyRecord if report_type == "feed" else WeightSample
        event_date = DailyRecord.record_date if report_type == "feed" else WeightSample.sampled_on
        event_statement = (
            select(
                model.id.label("record_id"),
                event_date.label("date"),
                Farm.name.label("farm"),
                Flock.id.label("flock_id"),
                Flock.name.label("flock"),
                *(
                    [DailyRecord.feed_used_kg, DailyRecord.deaths, DailyRecord.culling]
                    if report_type == "feed"
                    else [WeightSample.sample_size, WeightSample.average_weight_kg]
                ),
            )
            .join(Flock, (Flock.tenant_id == model.tenant_id) & (Flock.id == model.flock_id))
            .join(Farm, (Farm.tenant_id == Flock.tenant_id) & (Farm.id == Flock.farm_id))
            .where(
                model.tenant_id == tenant_id,
                event_date >= start_date,
                event_date <= end_date,
                *scope,
            )
            .order_by(event_date, Flock.name, model.id)
        )
        count = (
            db.scalar(select(func.count()).select_from(event_statement.subquery())) or 0
            if include_metadata
            else 0
        )
        event_rows = [
            dict(row._mapping) for row in db.execute(event_statement.limit(limit).offset(offset))
        ]
        if not include_metadata:
            return event_rows, count, {}
        if report_type == "feed":
            total = (
                db.scalar(
                    select(func.coalesce(func.sum(DailyRecord.feed_used_kg), 0))
                    .join(
                        Flock,
                        (Flock.tenant_id == DailyRecord.tenant_id)
                        & (Flock.id == DailyRecord.flock_id),
                    )
                    .where(
                        DailyRecord.tenant_id == tenant_id,
                        DailyRecord.record_date >= start_date,
                        DailyRecord.record_date <= end_date,
                        *scope,
                    )
                )
                or 0
            )
            return event_rows, count, {"feed_used_kg": total}
        sample_count = (
            db.scalar(
                select(func.coalesce(func.sum(WeightSample.sample_size), 0))
                .join(
                    Flock,
                    (Flock.tenant_id == WeightSample.tenant_id)
                    & (Flock.id == WeightSample.flock_id),
                )
                .where(
                    WeightSample.tenant_id == tenant_id,
                    WeightSample.sampled_on >= start_date,
                    WeightSample.sampled_on <= end_date,
                    *scope,
                )
            )
            or 0
        )
        return event_rows, count, {"sampled_birds": int(sample_count)}

    if report_type == "financial":
        farm_filter = (
            Farm.id == farm_id if farm_id else Farm.id.in_(select(Flock.farm_id).where(*scope))
        )
        flock_filter = (
            Flock.id == flock_id
            if flock_id
            else Flock.farm_id.in_(select(Flock.farm_id).where(*scope))
        )
        sales = (
            select(
                Sale.sale_on.label("date"),
                literal("sale").label("kind"),
                Farm.name.label("farm"),
                Flock.name.label("flock"),
                Buyer.name.label("party"),
                cast(Sale.birds, String).label("quantity"),
                Sale.amount_pkr.label("amount_pkr"),
            )
            .join(Farm, (Farm.tenant_id == Sale.tenant_id) & (Farm.id == Sale.farm_id))
            .join(Flock, (Flock.tenant_id == Sale.tenant_id) & (Flock.id == Sale.flock_id))
            .join(Buyer, (Buyer.tenant_id == Sale.tenant_id) & (Buyer.id == Sale.buyer_id))
            .where(
                Sale.tenant_id == tenant_id,
                Sale.sale_on.between(start_date, end_date),
                farm_filter,
                flock_filter,
            )
        )
        expenses = (
            select(
                Expense.incurred_on.label("date"),
                literal("expense").label("kind"),
                Farm.name.label("farm"),
                func.coalesce(Flock.name, literal("Farm-level")).label("flock"),
                Expense.description.label("party"),
                cast(literal(None), String).label("quantity"),
                Expense.amount_pkr.label("amount_pkr"),
            )
            .join(Farm, (Farm.tenant_id == Expense.tenant_id) & (Farm.id == Expense.farm_id))
            .outerjoin(
                Flock, (Flock.tenant_id == Expense.tenant_id) & (Flock.id == Expense.flock_id)
            )
            .where(
                Expense.tenant_id == tenant_id,
                Expense.incurred_on.between(start_date, end_date),
                farm_filter,
                *([Expense.flock_id == flock_id] if flock_id else []),
            )
        )
        payments = (
            select(
                SalePayment.paid_on.label("date"),
                literal("payment").label("kind"),
                Farm.name.label("farm"),
                Flock.name.label("flock"),
                Buyer.name.label("party"),
                cast(literal(None), String).label("quantity"),
                SalePayment.amount_pkr.label("amount_pkr"),
            )
            .join(
                Sale, (Sale.tenant_id == SalePayment.tenant_id) & (Sale.id == SalePayment.sale_id)
            )
            .join(Farm, (Farm.tenant_id == Sale.tenant_id) & (Farm.id == Sale.farm_id))
            .join(Flock, (Flock.tenant_id == Sale.tenant_id) & (Flock.id == Sale.flock_id))
            .join(Buyer, (Buyer.tenant_id == Sale.tenant_id) & (Buyer.id == Sale.buyer_id))
            .where(
                SalePayment.tenant_id == tenant_id,
                SalePayment.paid_on.between(start_date, end_date),
                farm_filter,
                flock_filter,
            )
        )
        purchases = (
            select(
                FeedPurchase.purchased_on.label("date"),
                literal("feed_purchase").label("kind"),
                Farm.name.label("farm"),
                literal("Farm feed stock").label("flock"),
                func.coalesce(FeedPurchase.supplier_name, literal("")).label("party"),
                cast(FeedPurchase.quantity_kg, String).label("quantity"),
                FeedPurchase.amount_pkr.label("amount_pkr"),
            )
            .join(
                Farm, (Farm.tenant_id == FeedPurchase.tenant_id) & (Farm.id == FeedPurchase.farm_id)
            )
            .where(
                FeedPurchase.tenant_id == tenant_id,
                FeedPurchase.purchased_on.between(start_date, end_date),
                farm_filter,
            )
        )
        financial_subquery = union_all(sales, expenses, payments, purchases).subquery()
        financial_query = select(financial_subquery).order_by(
            financial_subquery.c.date, financial_subquery.c.kind, financial_subquery.c.farm
        )
        count = (
            db.scalar(select(func.count()).select_from(financial_subquery)) or 0
            if include_metadata
            else 0
        )
        amount_totals: dict[Any, Any] = {}
        if include_metadata:
            amount_totals = dict(
                db.execute(
                    select(
                        financial_subquery.c.kind,
                        func.coalesce(func.sum(financial_subquery.c.amount_pkr), 0),
                    ).group_by(financial_subquery.c.kind)
                ).all()
            )
        financial_rows = [
            dict(row._mapping) for row in db.execute(financial_query.limit(limit).offset(offset))
        ]
        return financial_rows, count, amount_totals

    # Profit uses the existing approved cumulative-as-of calculation. The date
    # range end is the snapshot date; start_date filters which flocks are listed.
    placed_during_range = select(FlockPlacement.flock_id).where(
        FlockPlacement.tenant_id == tenant_id,
        FlockPlacement.placed_on.between(start_date, end_date),
    )
    profit_flock_statement = (
        select(Flock)
        .where(*scope, Flock.id.in_(placed_during_range))
        .order_by(Flock.name, Flock.id)
    )
    count = (
        db.scalar(select(func.count()).select_from(profit_flock_statement.subquery())) or 0
        if include_metadata
        else 0
    )
    selected_flocks = db.scalars(profit_flock_statement.limit(limit).offset(offset)).all()
    profit_rows = []
    for flock in selected_flocks:
        profit = flock_profit(flock.id, db, principal, end_date)
        profit_rows.append(profit.model_dump(mode="json"))
    return profit_rows, count, {"as_of": end_date.isoformat()}


@router.get("/{report_type}")
def read_report(
    report_type: ReportType,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("reports:read"))],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    farm_id: UUID | None = None,
    flock_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    karachi_today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    effective_end = end_date or karachi_today
    effective_start = start_date or effective_end - timedelta(days=29)
    if effective_end < effective_start:
        raise HTTPException(422, "End date must be on or after start date")
    rows, total, totals = _report_page(
        report_type, db, principal, effective_start, effective_end, farm_id, flock_id, limit, offset
    )
    return {"items": rows, "total": total, "totals": totals, "limit": limit, "offset": offset}


@router.get("/{report_type}/export.csv")
def export_report_csv(
    report_type: ReportType,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("reports:read"))],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    farm_id: UUID | None = None,
    flock_id: UUID | None = None,
) -> StreamingResponse:
    karachi_today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    effective_end = end_date or karachi_today
    effective_start = start_date or effective_end - timedelta(days=29)
    if effective_end < effective_start:
        raise HTTPException(422, "End date must be on or after start date")

    def rows() -> Any:
        import csv
        from io import StringIO

        offset = 0
        header: list[str] | None = None
        while True:
            page, total, _ = _report_page(
                report_type,
                db,
                principal,
                effective_start,
                effective_end,
                farm_id,
                flock_id,
                500,
                offset,
                include_metadata=False,
            )
            if header is None:
                header = list(page[0]) if page else ["No records"]
                buffer = StringIO()
                csv.writer(buffer).writerow(header)
                yield buffer.getvalue()
            for row in page:
                buffer = StringIO()
                csv.writer(buffer).writerow([row.get(column) for column in header])
                yield buffer.getvalue()
            offset += len(page)
            if not page or len(page) < 500:
                break

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="pouktry-{report_type}.csv"'},
    )
