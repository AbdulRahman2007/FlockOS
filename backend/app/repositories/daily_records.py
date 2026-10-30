from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.daily_records import DailyRecord, FeedPurchase, WeightSample
from app.models.farm_operations import Farm, Flock, FlockPlacement, Sale, TenantSettings
from app.repositories.base import TenantContext, TenantRepository


class DailyRepository(TenantRepository):
    def __init__(self, session: Session, context: TenantContext) -> None:
        super().__init__(session, context)
        self.session = session

    def flock(self, flock_id: UUID, *, lock: bool = False) -> Flock | None:
        statement: Select[Flock] = self.scoped(Flock).where(Flock.id == flock_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def farm_for_flock(self, flock: Flock) -> Farm | None:
        return self.session.scalar(self.scoped(Farm).where(Farm.id == flock.farm_id))

    def placements(self, flock_id: UUID) -> list[FlockPlacement]:
        return list(
            self.session.scalars(
                self.scoped(FlockPlacement)
                .where(FlockPlacement.flock_id == flock_id)
                .order_by(FlockPlacement.placed_on, FlockPlacement.id)
            ).all()
        )

    def records(self, flock_id: UUID) -> list[DailyRecord]:
        return list(
            self.session.scalars(
                self.scoped(DailyRecord)
                .where(DailyRecord.flock_id == flock_id)
                .order_by(DailyRecord.record_date, DailyRecord.id)
            ).all()
        )

    def sales(self, flock_id: UUID) -> list[Sale]:
        return list(
            self.session.scalars(
                self.scoped(Sale).where(Sale.flock_id == flock_id).order_by(Sale.sale_on, Sale.id)
            ).all()
        )

    def daily_records_page(
        self, flock_id: UUID, *, limit: int, offset: int, user_id: UUID | None = None
    ) -> tuple[list[DailyRecord], int]:
        statement = self.scoped(DailyRecord).where(DailyRecord.flock_id == flock_id)
        count_statement = (
            select(func.count())
            .select_from(DailyRecord)
            .where(
                DailyRecord.tenant_id == self._context.tenant_id, DailyRecord.flock_id == flock_id
            )
        )
        if user_id is not None:
            statement = statement.where(DailyRecord.created_by == user_id)
            count_statement = count_statement.where(DailyRecord.created_by == user_id)
        total = self.session.scalar(count_statement) or 0
        rows = self.session.scalars(
            statement.order_by(DailyRecord.record_date.desc(), DailyRecord.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return list(reversed(rows)), total

    def record_dates(self, flock_id: UUID) -> set[date]:
        return set(
            self.session.scalars(
                select(DailyRecord.record_date).where(
                    DailyRecord.tenant_id == self._context.tenant_id,
                    DailyRecord.flock_id == flock_id,
                )
            ).all()
        )

    def record(self, record_id: UUID, *, lock: bool = False) -> DailyRecord | None:
        statement: Select[DailyRecord] = self.scoped(DailyRecord).where(DailyRecord.id == record_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def record_for_date(self, flock_id: UUID, record_date: date) -> DailyRecord | None:
        return self.session.scalar(
            self.scoped(DailyRecord).where(
                DailyRecord.flock_id == flock_id, DailyRecord.record_date == record_date
            )
        )

    def idempotent_record(
        self, user_id: UUID, key: str, *, lock: bool = False
    ) -> DailyRecord | None:
        statement: Select[DailyRecord] = self.scoped(DailyRecord).where(
            DailyRecord.created_by == user_id, DailyRecord.idempotency_key == key
        )
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def weight_samples(self, flock_id: UUID) -> list[WeightSample]:
        return list(
            self.session.scalars(
                self.scoped(WeightSample)
                .where(WeightSample.flock_id == flock_id)
                .order_by(WeightSample.sampled_on, WeightSample.id)
            ).all()
        )

    def weight_samples_page(
        self, flock_id: UUID, *, limit: int, offset: int, user_id: UUID | None = None
    ) -> tuple[list[WeightSample], int]:
        statement = self.scoped(WeightSample).where(WeightSample.flock_id == flock_id)
        count_statement = (
            select(func.count())
            .select_from(WeightSample)
            .where(
                WeightSample.tenant_id == self._context.tenant_id, WeightSample.flock_id == flock_id
            )
        )
        if user_id is not None:
            statement = statement.where(WeightSample.created_by == user_id)
            count_statement = count_statement.where(WeightSample.created_by == user_id)
        total = self.session.scalar(count_statement) or 0
        rows = self.session.scalars(
            statement.order_by(WeightSample.sampled_on.desc(), WeightSample.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return list(reversed(rows)), total

    def weight_sample_for_date(self, flock_id: UUID, sampled_on: date) -> WeightSample | None:
        return self.session.scalar(
            self.scoped(WeightSample).where(
                WeightSample.flock_id == flock_id, WeightSample.sampled_on == sampled_on
            )
        )

    def feed_purchases(self, farm_id: UUID) -> list[FeedPurchase]:
        return list(
            self.session.scalars(
                self.scoped(FeedPurchase)
                .where(FeedPurchase.farm_id == farm_id)
                .order_by(FeedPurchase.purchased_on.desc(), FeedPurchase.created_at.desc())
            ).all()
        )

    def feed_purchases_page(
        self, farm_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[FeedPurchase], int]:
        statement = self.scoped(FeedPurchase).where(FeedPurchase.farm_id == farm_id)
        count_statement = (
            select(func.count())
            .select_from(FeedPurchase)
            .where(
                FeedPurchase.tenant_id == self._context.tenant_id, FeedPurchase.farm_id == farm_id
            )
        )
        total = self.session.scalar(count_statement) or 0
        rows = self.session.scalars(
            statement.order_by(FeedPurchase.purchased_on.desc(), FeedPurchase.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total

    def settings(self) -> TenantSettings | None:
        return self.session.get(TenantSettings, self._context.tenant_id)
