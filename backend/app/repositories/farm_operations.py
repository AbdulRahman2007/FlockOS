from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.farm_operations import Farm, Flock, FlockPlacement, Shed, TenantSettings
from app.models.identity import FarmAssignment
from app.repositories.base import TenantContext, TenantRepository


class FarmOperationsRepository(TenantRepository):
    def __init__(self, session: Session, context: TenantContext) -> None:
        super().__init__(session, context)
        self.session = session

    def farms(
        self, *, search: str, limit: int, offset: int, user_id: UUID | None
    ) -> tuple[list[Farm], int]:
        statement: Select[Farm] = self.scoped(Farm)
        count_statement = (
            select(func.count()).select_from(Farm).where(Farm.tenant_id == self._context.tenant_id)
        )
        if user_id is not None:
            assigned = select(FarmAssignment.farm_id).where(
                FarmAssignment.tenant_id == self._context.tenant_id,
                FarmAssignment.user_id == user_id,
            )
            statement = statement.where(Farm.id.in_(assigned))
            count_statement = count_statement.where(Farm.id.in_(assigned))
        if search:
            pattern = f"%{search}%"
            statement = statement.where(Farm.name.ilike(pattern))
            count_statement = count_statement.where(Farm.name.ilike(pattern))
        count = self.session.scalar(count_statement) or 0
        rows = self.session.scalars(
            statement.order_by(Farm.name, Farm.id).limit(limit).offset(offset)
        ).all()
        return list(rows), count

    def farm(self, farm_id: UUID) -> Farm | None:
        return self.session.scalar(self.scoped(Farm).where(Farm.id == farm_id))

    def sheds(
        self, farm_id: UUID, *, search: str, limit: int, offset: int
    ) -> tuple[list[Shed], int]:
        statement: Select[Shed] = self.scoped(Shed).where(Shed.farm_id == farm_id)
        count_statement = (
            select(func.count())
            .select_from(Shed)
            .where(Shed.tenant_id == self._context.tenant_id, Shed.farm_id == farm_id)
        )
        if search:
            pattern = f"%{search}%"
            statement = statement.where(Shed.name.ilike(pattern))
            count_statement = count_statement.where(Shed.name.ilike(pattern))
        count = self.session.scalar(count_statement) or 0
        rows = self.session.scalars(
            statement.order_by(Shed.name, Shed.id).limit(limit).offset(offset)
        ).all()
        return list(rows), count

    def shed(self, shed_id: UUID) -> Shed | None:
        return self.session.scalar(self.scoped(Shed).where(Shed.id == shed_id))

    def flocks(
        self,
        *,
        search: str,
        status: str | None,
        farm_id: UUID | None,
        user_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[Flock, int]], int]:
        statement = (
            self.scoped(Flock)
            .add_columns(func.coalesce(func.sum(FlockPlacement.bird_count), 0))
            .outerjoin(
                FlockPlacement,
                (FlockPlacement.tenant_id == Flock.tenant_id)
                & (FlockPlacement.flock_id == Flock.id),
            )
        )
        count_statement = (
            select(func.count(func.distinct(Flock.id)))
            .select_from(Flock)
            .where(Flock.tenant_id == self._context.tenant_id)
        )
        if user_id is not None:
            assigned = select(FarmAssignment.farm_id).where(
                FarmAssignment.tenant_id == self._context.tenant_id,
                FarmAssignment.user_id == user_id,
            )
            statement = statement.where(Flock.farm_id.in_(assigned))
            count_statement = count_statement.where(Flock.farm_id.in_(assigned))
        if farm_id is not None:
            statement = statement.where(Flock.farm_id == farm_id)
            count_statement = count_statement.where(Flock.farm_id == farm_id)
        if status is not None:
            statement = statement.where(Flock.status == status)
            count_statement = count_statement.where(Flock.status == status)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(Flock.name.ilike(pattern))
            count_statement = count_statement.where(Flock.name.ilike(pattern))
        count = self.session.scalar(count_statement) or 0
        rows = self.session.execute(
            statement.group_by(Flock.id)
            .order_by(Flock.created_at.desc(), Flock.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [(row[0], row[1]) for row in rows], count

    def flock(self, flock_id: UUID) -> Flock | None:
        return self.session.scalar(self.scoped(Flock).where(Flock.id == flock_id))

    def placements(self, flock_id: UUID) -> list[FlockPlacement]:
        return list(
            self.session.scalars(
                self.scoped(FlockPlacement)
                .where(FlockPlacement.flock_id == flock_id)
                .order_by(FlockPlacement.placed_on, FlockPlacement.id)
            ).all()
        )

    def settings(self) -> TenantSettings | None:
        return self.session.get(TenantSettings, self._context.tenant_id)

    def farm_has_children(self, farm_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Shed)
                .where(Shed.tenant_id == self._context.tenant_id, Shed.farm_id == farm_id)
            )
            != 0
        )

    def shed_has_flocks(self, shed_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Flock)
                .where(Flock.tenant_id == self._context.tenant_id, Flock.shed_id == shed_id)
            )
            != 0
        )

    def flock_has_activity(self, flock_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(FlockPlacement)
                .where(
                    FlockPlacement.tenant_id == self._context.tenant_id,
                    FlockPlacement.flock_id == flock_id,
                )
            )
            != 0
        )

    def placed_birds(self, flock_id: UUID) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.sum(FlockPlacement.bird_count), 0)).where(
                    FlockPlacement.tenant_id == self._context.tenant_id,
                    FlockPlacement.flock_id == flock_id,
                )
            )
            or 0
        )

    def placement_exists_on(self, flock_id: UUID, placed_on: date) -> bool:
        return (
            self.session.scalar(
                select(FlockPlacement.id).where(
                    FlockPlacement.tenant_id == self._context.tenant_id,
                    FlockPlacement.flock_id == flock_id,
                    FlockPlacement.placed_on == placed_on,
                )
            )
            is not None
        )
