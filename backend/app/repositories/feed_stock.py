from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Select, cast, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.domain.calculations import FeedStockMovement
from app.models.daily_records import DailyRecord, FeedPurchase, FeedStockEvent
from app.models.farm_operations import Farm, Flock
from app.repositories.base import TenantContext, TenantRepository


class FeedStockRepository(TenantRepository):
    def __init__(self, session: Session, context: TenantContext) -> None:
        super().__init__(session, context)
        self.session = session

    def farm(self, farm_id: UUID, *, lock: bool = False) -> Farm | None:
        statement: Select[Farm] = self.scoped(Farm).where(Farm.id == farm_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def stock_events(self, farm_id: UUID, *, as_of: date | None = None) -> list[FeedStockEvent]:
        statement = self.scoped(FeedStockEvent).where(FeedStockEvent.farm_id == farm_id)
        if as_of is not None:
            statement = statement.where(FeedStockEvent.occurred_on <= as_of)
        return list(
            self.session.scalars(statement.order_by(FeedStockEvent.occurred_on, FeedStockEvent.id))
        )

    def purchases(self, farm_id: UUID, *, as_of: date | None = None) -> list[FeedPurchase]:
        statement = self.scoped(FeedPurchase).where(FeedPurchase.farm_id == farm_id)
        if as_of is not None:
            statement = statement.where(FeedPurchase.purchased_on <= as_of)
        return list(self.session.scalars(statement.order_by(FeedPurchase.purchased_on, FeedPurchase.id)))

    def usage(self, farm_id: UUID, *, as_of: date | None = None) -> list[DailyRecord]:
        statement = (
            select(DailyRecord)
            .join(Flock, (Flock.tenant_id == DailyRecord.tenant_id) & (Flock.id == DailyRecord.flock_id))
            .where(DailyRecord.tenant_id == self._context.tenant_id, Flock.farm_id == farm_id)
        )
        if as_of is not None:
            statement = statement.where(DailyRecord.record_date <= as_of)
        return list(
            self.session.scalars(statement.order_by(DailyRecord.record_date, DailyRecord.id))
        )

    def movements(
        self,
        farm_id: UUID,
        *,
        as_of: date | None = None,
        exclude_usage_id: UUID | None = None,
    ) -> list[FeedStockMovement]:
        result = [
            FeedStockMovement(item.occurred_on, item.event_type, item.quantity_kg)
            for item in self.stock_events(farm_id, as_of=as_of)
        ]
        result.extend(
            FeedStockMovement(item.purchased_on, "purchase", item.quantity_kg)
            for item in self.purchases(farm_id, as_of=as_of)
        )
        result.extend(
            FeedStockMovement(item.record_date, "usage", item.feed_used_kg)
            for item in self.usage(farm_id, as_of=as_of)
            if item.feed_used_kg > 0 and item.id != exclude_usage_id
        )
        return result

    def movement_page(
        self, farm_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        tenant_id = self._context.tenant_id
        rows = union_all(
            select(
                FeedStockEvent.id.label("id"),
                FeedStockEvent.occurred_on.label("occurred_on"),
                FeedStockEvent.event_type.label("event_type"),
                FeedStockEvent.quantity_kg.label("quantity_kg"),
                FeedStockEvent.reason.label("reason"),
                FeedStockEvent.created_by.label("created_by"),
            ).where(FeedStockEvent.tenant_id == tenant_id, FeedStockEvent.farm_id == farm_id),
            select(
                FeedPurchase.id,
                FeedPurchase.purchased_on,
                literal("purchase"),
                FeedPurchase.quantity_kg,
                FeedPurchase.notes,
                FeedPurchase.created_by,
            ).where(FeedPurchase.tenant_id == tenant_id, FeedPurchase.farm_id == farm_id),
            select(
                DailyRecord.id,
                DailyRecord.record_date,
                literal("usage"),
                DailyRecord.feed_used_kg,
                cast(literal(None), FeedStockEvent.reason.type),
                DailyRecord.updated_by,
            )
            .join(Flock, (Flock.tenant_id == DailyRecord.tenant_id) & (Flock.id == DailyRecord.flock_id))
            .where(
                DailyRecord.tenant_id == tenant_id,
                Flock.farm_id == farm_id,
                DailyRecord.feed_used_kg > 0,
            ),
        ).subquery("feed_stock_movement_facts")
        total = self.session.scalar(select(func.count()).select_from(rows)) or 0
        selected = self.session.execute(
            select(rows)
            .order_by(rows.c.occurred_on.desc(), rows.c.event_type, rows.c.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [dict(row._mapping) for row in selected], int(total)
