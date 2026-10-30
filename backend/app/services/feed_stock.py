import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.authz import Principal
from app.domain.calculations import (
    FeedStockBalance,
    FeedStockMovement,
    calculate_feed_cover_days,
    calculate_feed_stock,
    feed_cover_below_threshold,
    calculate_feed_stock_ledger,
)
from app.models.daily_records import DailyRecord, FeedPurchase, FeedStockEvent
from app.models.farm_operations import Farm, Flock, TenantSettings
from app.repositories.base import TenantContext
from app.repositories.feed_stock import FeedStockRepository
from app.schemas.feed_stock import FeedStockEventCreate, FeedStockSnapshotRead
from app.services.audit import record_audit

ZERO = Decimal("0")


class FeedStockError(ValueError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _repository(session: Session, tenant_id: UUID) -> FeedStockRepository:
    return FeedStockRepository(session, TenantContext(tenant_id))


def _checked_ledger(movements: list[FeedStockMovement]) -> tuple[FeedStockBalance, ...]:
    try:
        return calculate_feed_stock_ledger(movements)
    except ValueError as error:
        message = str(error)
        code = 409 if "opening stock" in message else 422
        raise FeedStockError(code, message) from None


def validate_feed_stock_change(
    session: Session,
    *,
    tenant_id: UUID,
    farm_id: UUID,
    movement: FeedStockMovement | None,
    exclude_usage_id: UUID | None = None,
    lock_farm: bool = True,
) -> None:
    """Serialize stock writes on a farm and reject a fact that breaks its ledger."""
    repo = _repository(session, tenant_id)
    farm = repo.farm(farm_id, lock=lock_farm)
    if farm is None:
        raise FeedStockError(404, "Farm not found")
    movements = repo.movements(farm_id, exclude_usage_id=exclude_usage_id)
    if movement is not None and movement.kind != "opening" and not any(
        item.kind == "opening" for item in movements
    ):
        # A farm without an opening fact has unknown stock, not an assumed zero.
        # Its history is validated when the owner records the opening balance.
        return
    if movement is not None:
        movements.append(movement)
    _checked_ledger(movements)


def create_feed_stock_event(
    session: Session,
    principal: Principal,
    farm_id: UUID,
    payload: FeedStockEventCreate,
) -> FeedStockEvent:
    if principal.tenant_id is None:
        raise FeedStockError(403, "Not permitted")
    row = FeedStockEvent(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        event_type=payload.event_type,
        occurred_on=payload.occurred_on,
        quantity_kg=payload.quantity_kg,
        reason=payload.reason,
        created_by=principal.user_id,
        created_at=datetime.now(UTC),
    )
    validate_feed_stock_change(
        session,
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        movement=FeedStockMovement(payload.occurred_on, payload.event_type, payload.quantity_kg),
    )
    session.add(row)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action=f"feed_stock.{payload.event_type}",
        entity_type="feed_stock_event",
        entity_id=str(row.id),
        new_value=json.dumps(payload.model_dump(mode="json"), sort_keys=True),
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return row


def feed_stock_snapshots(
    session: Session,
    *,
    tenant_id: UUID,
    farm_ids: list[UUID],
    as_of: date,
) -> dict[UUID, FeedStockSnapshotRead]:
    if not farm_ids:
        return {}
    settings = session.get(TenantSettings, tenant_id)
    window_days = settings.feed_cover_usage_window_days if settings else 3
    threshold = settings.feed_cover_threshold_days if settings else Decimal("3")
    openings = (
        select(FeedStockEvent.farm_id, func.count(FeedStockEvent.id).label("opening_count"))
        .where(
            FeedStockEvent.tenant_id == tenant_id,
            FeedStockEvent.farm_id.in_(farm_ids),
            FeedStockEvent.event_type == "opening",
            FeedStockEvent.occurred_on <= as_of,
        )
        .group_by(FeedStockEvent.farm_id)
        .subquery()
    )
    event_totals = (
        select(
            FeedStockEvent.farm_id,
            func.sum(
                case((FeedStockEvent.event_type == "opening", FeedStockEvent.quantity_kg), else_=0)
            ).label("opening"),
            func.sum(
                case(
                    (FeedStockEvent.event_type == "return_to_stock", FeedStockEvent.quantity_kg),
                    else_=0,
                )
            ).label("returns_in"),
            func.sum(
                case(
                    (
                        FeedStockEvent.event_type == "return_to_supplier",
                        FeedStockEvent.quantity_kg,
                    ),
                    else_=0,
                )
            ).label("returns_out"),
            func.sum(
                case(
                    (FeedStockEvent.event_type == "adjustment", FeedStockEvent.quantity_kg),
                    else_=0,
                )
            ).label("adjustments"),
        )
        .where(
            FeedStockEvent.tenant_id == tenant_id,
            FeedStockEvent.farm_id.in_(farm_ids),
            FeedStockEvent.occurred_on <= as_of,
        )
        .group_by(FeedStockEvent.farm_id)
        .subquery()
    )
    purchases = (
        select(FeedPurchase.farm_id, func.sum(FeedPurchase.quantity_kg).label("purchases"))
        .where(
            FeedPurchase.tenant_id == tenant_id,
            FeedPurchase.farm_id.in_(farm_ids),
            FeedPurchase.purchased_on <= as_of,
        )
        .group_by(FeedPurchase.farm_id)
        .subquery()
    )
    usage = (
        select(Flock.farm_id, func.sum(DailyRecord.feed_used_kg).label("usage"))
        .join(Flock, (Flock.tenant_id == DailyRecord.tenant_id) & (Flock.id == DailyRecord.flock_id))
        .where(
            DailyRecord.tenant_id == tenant_id,
            Flock.farm_id.in_(farm_ids),
            DailyRecord.record_date <= as_of,
        )
        .group_by(Flock.farm_id)
        .subquery()
    )
    recent_usage = (
        select(Flock.farm_id, func.sum(DailyRecord.feed_used_kg).label("usage"))
        .join(Flock, (Flock.tenant_id == DailyRecord.tenant_id) & (Flock.id == DailyRecord.flock_id))
        .where(
            DailyRecord.tenant_id == tenant_id,
            Flock.farm_id.in_(farm_ids),
            DailyRecord.record_date.between(as_of - timedelta(days=window_days - 1), as_of),
        )
        .group_by(Flock.farm_id)
        .subquery()
    )
    statement = (
        select(
            Farm.id,
            openings.c.opening_count,
            event_totals.c.opening,
            event_totals.c.returns_in,
            event_totals.c.returns_out,
            event_totals.c.adjustments,
            purchases.c.purchases,
            usage.c.usage,
            recent_usage.c.usage.label("recent_usage"),
        )
        .select_from(Farm)
        .outerjoin(openings, openings.c.farm_id == Farm.id)
        .outerjoin(event_totals, event_totals.c.farm_id == Farm.id)
        .outerjoin(purchases, purchases.c.farm_id == Farm.id)
        .outerjoin(usage, usage.c.farm_id == Farm.id)
        .outerjoin(recent_usage, recent_usage.c.farm_id == Farm.id)
        .where(Farm.tenant_id == tenant_id, Farm.id.in_(farm_ids))
    )
    rows = {row.id: row for row in session.execute(statement).all()}
    snapshots: dict[UUID, FeedStockSnapshotRead] = {}
    for farm_id in farm_ids:
        row = rows.get(farm_id)
        if row is None:
            continue
        if not row.opening_count:
            snapshots[farm_id] = FeedStockSnapshotRead(
                farm_id=farm_id,
                as_of=as_of,
                stock_kg=None,
                feed_cover_days=None,
                status="unavailable_missing_opening_stock",
            )
            continue
        try:
            stock = calculate_feed_stock(
                Decimal(row.opening or 0),
                Decimal(row.purchases or 0),
                Decimal(row.usage or 0),
                Decimal(row.returns_in or 0),
                Decimal(row.adjustments or 0),
                Decimal(row.returns_out or 0),
            )
        except ValueError:
            snapshots[farm_id] = FeedStockSnapshotRead(
                farm_id=farm_id,
                as_of=as_of,
                stock_kg=None,
                feed_cover_days=None,
                status="unavailable_invalid_stock_history",
            )
            continue
        cover = calculate_feed_cover_days(
            stock, Decimal(row.recent_usage or 0), usage_window_days=window_days
        )
        snapshots[farm_id] = FeedStockSnapshotRead(
            farm_id=farm_id,
            as_of=as_of,
            stock_kg=stock,
            feed_cover_days=cover,
            status=(
                "low_feed_cover"
                if feed_cover_below_threshold(cover, threshold)
                else "available" if cover is not None else "unavailable_missing_recent_usage"
            ),
        )
    return snapshots


def feed_stock_snapshot(
    session: Session, *, tenant_id: UUID, farm_id: UUID, as_of: date
) -> FeedStockSnapshotRead:
    return feed_stock_snapshots(
        session, tenant_id=tenant_id, farm_ids=[farm_id], as_of=as_of
    )[farm_id]
