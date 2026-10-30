import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.v1.farm_access import require_farm_scope, tenant_repository
from app.core.authz import Principal, get_db, require_permission
from app.domain.calculations import (
    DailyBirdFacts,
    allocate_farm_cost,
    calculate_bird_days_for_period,
    calculate_bird_ledger,
    calculate_profit,
)
from app.models.daily_records import WeightSample
from app.models.farm_operations import (
    Buyer,
    Expense,
    ExpenseEligibleFlock,
    Flock,
    MarketPrice,
    Sale,
    SalePayment,
    Supplier,
)
from app.repositories.base import TenantContext
from app.repositories.daily_records import DailyRepository
from app.schemas.finance import (
    ExpenseCreate,
    ExpenseUpdate,
    FlockProfitRead,
    PartyCreate,
    PartyRead,
    PaymentCreate,
    SaleCreate,
    SaleRead,
    SaleUpdate,
)
from app.services.audit import record_audit
from app.services.daily_records import _ledger_facts

router = APIRouter(tags=["finance"])
Db = Annotated[Session, Depends(get_db)]


def _party(
    db: Session, principal: Principal, data: PartyCreate, model: type[Buyer] | type[Supplier]
) -> PartyRead:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    now = datetime.now(UTC)
    row = model(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        name=data.name,
        phone=data.phone,
        created_by=principal.user_id,
        created_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "A party with this name already exists") from None
    return PartyRead(id=row.id, name=row.name, phone=row.phone)


@router.post("/buyers", response_model=PartyRead, status_code=201)
def create_buyer(
    data: PartyCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:write"))],
) -> PartyRead:
    return _party(db, principal, data, Buyer)


@router.get("/buyers", response_model=list[PartyRead])
def list_buyers(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PartyRead]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    rows = db.scalars(
        select(Buyer)
        .where(Buyer.tenant_id == principal.tenant_id)
        .order_by(Buyer.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return [PartyRead(id=row.id, name=row.name, phone=row.phone) for row in rows]


@router.post("/suppliers", response_model=PartyRead, status_code=201)
def create_supplier(
    data: PartyCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:write"))],
) -> PartyRead:
    return _party(db, principal, data, Supplier)


@router.get("/suppliers", response_model=list[PartyRead])
def list_suppliers(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PartyRead]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    rows = db.scalars(
        select(Supplier)
        .where(Supplier.tenant_id == principal.tenant_id)
        .order_by(Supplier.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return [PartyRead(id=row.id, name=row.name, phone=row.phone) for row in rows]


@router.get("/farms/{farm_id}/sales", response_model=list[SaleRead])
def list_sales(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SaleRead]:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    rows = db.scalars(
        select(Sale)
        .where(Sale.tenant_id == principal.tenant_id, Sale.farm_id == farm_id)
        .order_by(Sale.sale_on.desc(), Sale.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [SaleRead.model_validate(row, from_attributes=True) for row in rows]


@router.get("/farms/{farm_id}/expenses")
def list_expenses(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    rows = db.scalars(
        select(Expense)
        .where(Expense.tenant_id == principal.tenant_id, Expense.farm_id == farm_id)
        .order_by(Expense.incurred_on.desc(), Expense.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": row.id,
            "scope": row.scope,
            "flock_id": row.flock_id,
            "incurred_on": row.incurred_on,
            "amount_pkr": row.amount_pkr,
            "description": row.description,
            "supplier_id": row.supplier_id,
            "allocation_start": row.allocation_start,
            "allocation_end": row.allocation_end,
            "version": row.version,
        }
        for row in rows
    ]


@router.post("/farms/{farm_id}/expenses", status_code=201)
def create_expense(
    farm_id: UUID,
    data: ExpenseCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:write"))],
) -> dict[str, Any]:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    if (
        data.flock_id is not None
        and db.scalar(
            select(Flock.id).where(
                Flock.tenant_id == principal.tenant_id,
                Flock.id == data.flock_id,
                Flock.farm_id == farm_id,
            )
        )
        is None
    ):
        raise HTTPException(404, "Flock not found")
    if (
        data.supplier_id is not None
        and db.scalar(
            select(Supplier.id).where(
                Supplier.tenant_id == principal.tenant_id, Supplier.id == data.supplier_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Supplier not found")
    eligible_ids = data.eligible_flock_ids if data.scope == "farm" else []
    if eligible_ids:
        eligible_rows = db.scalars(
            select(Flock.id).where(
                Flock.tenant_id == principal.tenant_id,
                Flock.farm_id == farm_id,
                Flock.id.in_(eligible_ids),
            )
        ).all()
        if set(eligible_rows) != set(eligible_ids):
            raise HTTPException(422, "Eligible flocks must belong to this farm")
    expense_values = data.model_dump(exclude={"eligible_flock_ids"})
    row = Expense(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        **expense_values,
        created_by=principal.user_id,
        updated_by=principal.user_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    for eligible_flock_id in eligible_ids:
        db.add(
            ExpenseEligibleFlock(
                id=uuid4(),
                tenant_id=principal.tenant_id,
                farm_id=farm_id,
                expense_id=row.id,
                flock_id=eligible_flock_id,
            )
        )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="expense.create",
        entity_type="expense",
        entity_id=str(row.id),
        new_value=json.dumps(data.model_dump(mode="json"), sort_keys=True),
    )
    db.commit()
    return {
        "id": row.id,
        "scope": row.scope,
        "flock_id": row.flock_id,
        "amount_pkr": row.amount_pkr,
        "version": row.version,
    }


@router.patch("/expenses/{expense_id}")
def update_expense(
    expense_id: UUID,
    data: ExpenseUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("expenses:write"))],
) -> dict[str, Any]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    row = db.scalar(
        select(Expense)
        .where(Expense.tenant_id == principal.tenant_id, Expense.id == expense_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Expense not found")
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, row.farm_id)
    if row.version != data.expected_version:
        raise HTTPException(409, "This expense changed. Reload it before editing.")
    if data.flock_id is not None:
        target_flock = db.scalar(
            select(Flock).where(
                Flock.tenant_id == principal.tenant_id,
                Flock.farm_id == row.farm_id,
                Flock.id == data.flock_id,
            )
        )
        if target_flock is None:
            raise HTTPException(404, "Flock not found")
        if target_flock.status != "active":
            raise HTTPException(423, "Closed flocks are locked")
    if (
        data.supplier_id is not None
        and db.scalar(
            select(Supplier.id).where(
                Supplier.tenant_id == principal.tenant_id, Supplier.id == data.supplier_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Supplier not found")
    eligible_ids = data.eligible_flock_ids if data.scope == "farm" else []
    if eligible_ids:
        valid_ids = db.scalars(
            select(Flock.id).where(
                Flock.tenant_id == principal.tenant_id,
                Flock.farm_id == row.farm_id,
                Flock.id.in_(eligible_ids),
            )
        ).all()
        if set(valid_ids) != set(eligible_ids):
            raise HTTPException(422, "Eligible flocks must belong to this farm")
    old_eligible_ids = db.scalars(
        select(ExpenseEligibleFlock.flock_id).where(
            ExpenseEligibleFlock.tenant_id == principal.tenant_id,
            ExpenseEligibleFlock.expense_id == row.id,
        )
    ).all()
    old_value = {
        "scope": row.scope,
        "flock_id": str(row.flock_id) if row.flock_id else None,
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "incurred_on": row.incurred_on.isoformat(),
        "allocation_start": row.allocation_start.isoformat() if row.allocation_start else None,
        "allocation_end": row.allocation_end.isoformat() if row.allocation_end else None,
        "eligible_flock_ids": sorted(str(item) for item in old_eligible_ids),
        "amount_pkr": str(row.amount_pkr),
        "description": row.description,
        "version": row.version,
    }
    values = data.model_dump(exclude={"expected_version", "eligible_flock_ids"})
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by = principal.user_id
    db.execute(
        delete(ExpenseEligibleFlock).where(
            ExpenseEligibleFlock.tenant_id == principal.tenant_id,
            ExpenseEligibleFlock.expense_id == row.id,
        )
    )
    for eligible_flock_id in eligible_ids:
        db.add(
            ExpenseEligibleFlock(
                id=uuid4(),
                tenant_id=principal.tenant_id,
                farm_id=row.farm_id,
                expense_id=row.id,
                flock_id=eligible_flock_id,
            )
        )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="expense.update",
        entity_type="expense",
        entity_id=str(row.id),
        old_value=json.dumps(old_value, sort_keys=True),
        new_value=json.dumps(data.model_dump(mode="json"), sort_keys=True),
    )
    try:
        db.commit()
    except (IntegrityError, StaleDataError):
        db.rollback()
        raise HTTPException(409, "This expense changed or conflicts with existing data") from None
    return {"id": row.id, "scope": row.scope, "amount_pkr": row.amount_pkr, "version": row.version}


@router.post("/farms/{farm_id}/sales", response_model=SaleRead, status_code=201)
def create_sale(
    farm_id: UUID,
    data: SaleCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:write"))],
) -> SaleRead:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    context_repo = DailyRepository(db, TenantContext(principal.tenant_id))
    flock = context_repo.flock(data.flock_id, lock=True)
    if flock is None or flock.farm_id != farm_id:
        raise HTTPException(404, "Flock not found")
    if flock.status != "active":
        raise HTTPException(423, "Closed flocks are locked")
    if (
        db.scalar(
            select(Buyer.id).where(
                Buyer.tenant_id == principal.tenant_id, Buyer.id == data.buyer_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Buyer not found")
    placements = context_repo.placements(flock.id)
    if not placements or data.sale_on < min(row.placed_on for row in placements):
        raise HTTPException(422, "Sale date cannot be before flock placement")
    records = context_repo.records(flock.id)
    sales = context_repo.sales(flock.id)
    movements: dict[date, dict[str, int]] = {}
    ordered_placements = sorted(
        placements, key=lambda placement: (placement.placed_on, str(placement.id))
    )
    for placement in ordered_placements[1:]:
        day = movements.setdefault(placement.placed_on, {})
        day["transferred_in"] = day.get("transferred_in", 0) + placement.bird_count
    for record in records:
        day = movements.setdefault(record.record_date, {})
        day["deaths"] = day.get("deaths", 0) + record.deaths
        day["culling"] = day.get("culling", 0) + record.culling
    for sale_fact in sales:
        day = movements.setdefault(sale_fact.sale_on, {})
        day["sold"] = day.get("sold", 0) + sale_fact.birds
    day = movements.setdefault(data.sale_on, {})
    day["sold"] = day.get("sold", 0) + data.birds
    try:
        calculate_bird_ledger(
            ordered_placements[0].bird_count,
            [DailyBirdFacts(day=key, **val) for key, val in movements.items()],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    now = datetime.now(UTC)
    row = Sale(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        flock_id=flock.id,
        buyer_id=data.buyer_id,
        sale_on=data.sale_on,
        birds=data.birds,
        total_weight_kg=data.total_weight_kg,
        rate_per_kg_pkr=data.rate_per_kg_pkr,
        amount_pkr=data.amount_pkr,
        version=1,
        created_by=principal.user_id,
        updated_by=principal.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="sale.create",
        entity_type="sale",
        entity_id=str(row.id),
        new_value=json.dumps(data.model_dump(mode="json"), sort_keys=True),
    )
    if data.amount_paid_pkr > 0:
        payment = SalePayment(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            sale_id=row.id,
            paid_on=data.sale_on,
            amount_pkr=data.amount_paid_pkr,
            created_by=principal.user_id,
            created_at=now,
        )
        db.add(payment)
        record_audit(
            db,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            action="sale_payment.create",
            entity_type="sale_payment",
            entity_id=str(payment.id),
            new_value=str(data.amount_paid_pkr),
        )
    db.commit()
    return SaleRead.model_validate(row, from_attributes=True)


@router.post("/sales/{sale_id}/payments", status_code=201)
def add_payment(
    sale_id: UUID,
    data: PaymentCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:write"))],
) -> dict[str, Any]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    sale = db.scalar(
        select(Sale)
        .where(Sale.tenant_id == principal.tenant_id, Sale.id == sale_id)
        .with_for_update()
    )
    if sale is None:
        raise HTTPException(404, "Sale not found")
    row = SalePayment(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        sale_id=sale_id,
        paid_on=data.paid_on,
        amount_pkr=data.amount_pkr,
        reference=data.reference,
        created_by=principal.user_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="sale_payment.create",
        entity_type="sale_payment",
        entity_id=str(row.id),
        new_value=json.dumps(data.model_dump(mode="json"), sort_keys=True),
    )
    db.commit()
    return {"id": row.id, "sale_id": sale_id, "amount_pkr": row.amount_pkr}


@router.patch("/sales/{sale_id}", response_model=SaleRead)
def update_sale(
    sale_id: UUID,
    data: SaleUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:write"))],
) -> SaleRead:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    sale = db.scalar(
        select(Sale)
        .where(Sale.tenant_id == principal.tenant_id, Sale.id == sale_id)
        .with_for_update()
    )
    if sale is None:
        raise HTTPException(404, "Sale not found")
    repo = DailyRepository(db, TenantContext(principal.tenant_id))
    flock = repo.flock(sale.flock_id, lock=True)
    if flock is None:
        raise HTTPException(404, "Sale not found")
    if flock.status != "active":
        raise HTTPException(423, "Closed flocks are locked")
    if sale.version != data.expected_version:
        raise HTTPException(409, "This sale changed. Reload it before editing.")
    if (
        db.scalar(
            select(Buyer.id).where(
                Buyer.tenant_id == principal.tenant_id, Buyer.id == data.buyer_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Buyer not found")
    placements = repo.placements(flock.id)
    if not placements or data.sale_on < min(item.placed_on for item in placements):
        raise HTTPException(422, "Sale date cannot be before flock placement")
    records = repo.records(flock.id)
    other_sales = [item for item in repo.sales(flock.id) if item.id != sale.id]
    ordered_placements = sorted(placements, key=lambda item: (item.placed_on, str(item.id)))
    movements: dict[date, dict[str, int]] = {}
    for placement in ordered_placements[1:]:
        day = movements.setdefault(placement.placed_on, {})
        day["transferred_in"] = day.get("transferred_in", 0) + placement.bird_count
    for record in records:
        day = movements.setdefault(record.record_date, {})
        day["deaths"] = day.get("deaths", 0) + record.deaths
        day["culling"] = day.get("culling", 0) + record.culling
    for old_sale in other_sales:
        day = movements.setdefault(old_sale.sale_on, {})
        day["sold"] = day.get("sold", 0) + old_sale.birds
    day = movements.setdefault(data.sale_on, {})
    day["sold"] = day.get("sold", 0) + data.birds
    try:
        calculate_bird_ledger(
            ordered_placements[0].bird_count,
            [DailyBirdFacts(day=event_day, **values) for event_day, values in movements.items()],
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    old_value = {
        "buyer_id": str(sale.buyer_id),
        "sale_on": sale.sale_on.isoformat(),
        "birds": sale.birds,
        "total_weight_kg": str(sale.total_weight_kg),
        "rate_per_kg_pkr": str(sale.rate_per_kg_pkr),
        "amount_pkr": str(sale.amount_pkr),
        "version": sale.version,
    }
    for key in (
        "buyer_id",
        "sale_on",
        "birds",
        "total_weight_kg",
        "rate_per_kg_pkr",
        "amount_pkr",
    ):
        setattr(sale, key, getattr(data, key))
    sale.updated_by = principal.user_id
    sale.updated_at = datetime.now(UTC)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="sale.update",
        entity_type="sale",
        entity_id=str(sale.id),
        old_value=json.dumps(old_value, sort_keys=True),
        new_value=json.dumps(data.model_dump(mode="json"), sort_keys=True),
    )
    try:
        db.commit()
    except (IntegrityError, StaleDataError):
        db.rollback()
        raise HTTPException(409, "This sale changed or conflicts with existing data") from None
    return SaleRead.model_validate(sale, from_attributes=True)


@router.get("/buyers/outstanding")
def buyer_outstanding(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("sales:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    sales = (
        select(Sale.buyer_id.label("buyer_id"), func.sum(Sale.amount_pkr).label("sold"))
        .where(Sale.tenant_id == principal.tenant_id)
        .group_by(Sale.buyer_id)
        .subquery()
    )
    paid = (
        select(Sale.buyer_id.label("buyer_id"), func.sum(SalePayment.amount_pkr).label("paid"))
        .join(Sale, (Sale.tenant_id == SalePayment.tenant_id) & (Sale.id == SalePayment.sale_id))
        .where(Sale.tenant_id == principal.tenant_id)
        .group_by(Sale.buyer_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Buyer.id,
            Buyer.name,
            (func.coalesce(sales.c.sold, 0) - func.coalesce(paid.c.paid, 0)).label("outstanding"),
        )
        .outerjoin(sales, sales.c.buyer_id == Buyer.id)
        .outerjoin(paid, paid.c.buyer_id == Buyer.id)
        .where(Buyer.tenant_id == principal.tenant_id)
        .order_by(Buyer.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {"buyer_id": row.id, "buyer_name": row.name, "outstanding_pkr": row.outstanding}
        for row in rows
    ]


@router.get("/flocks/{flock_id}/profit", response_model=FlockProfitRead)
def flock_profit(
    flock_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("reports:read"))],
    as_of: date | None = None,
) -> FlockProfitRead:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    report_date = as_of or datetime.now(ZoneInfo("Asia/Karachi")).date()
    flock = db.scalar(
        select(Flock).where(Flock.tenant_id == principal.tenant_id, Flock.id == flock_id)
    )
    if flock is None:
        raise HTTPException(404, "Flock not found")
    farm_repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, farm_repo, flock.farm_id)
    repo = DailyRepository(db, TenantContext(principal.tenant_id))

    def facts_for(
        target_flock_id: UUID, cutoff: date
    ) -> tuple[int, tuple[DailyBirdFacts, ...], date | None]:
        target_placements = [
            item for item in repo.placements(target_flock_id) if item.placed_on <= cutoff
        ]
        if not target_placements:
            return 0, (), None
        records = [item for item in repo.records(target_flock_id) if item.record_date <= cutoff]
        sale_rows = [item for item in repo.sales(target_flock_id) if item.sale_on <= cutoff]
        placed, facts = _ledger_facts(target_placements, records, sale_rows)
        return placed, tuple(facts), target_placements[0].placed_on

    placed, daily_facts, placed_on = facts_for(flock.id, report_date)
    if placed_on is None:
        raise HTTPException(409, "Flock has no placement on or before the report date")
    ledger = calculate_bird_ledger(placed, daily_facts)
    live_birds = ledger[-1].closing_birds if ledger else placed
    price = db.scalar(
        select(MarketPrice.price_per_kg_pkr)
        .where(
            MarketPrice.tenant_id == principal.tenant_id,
            MarketPrice.farm_id == flock.farm_id,
            MarketPrice.effective_on <= report_date,
        )
        .order_by(MarketPrice.effective_on.desc(), MarketPrice.id.desc())
        .limit(1)
    )
    average_weight = db.scalar(
        select(WeightSample.average_weight_kg)
        .where(
            WeightSample.tenant_id == principal.tenant_id,
            WeightSample.flock_id == flock.id,
            WeightSample.sampled_on <= report_date,
        )
        .order_by(WeightSample.sampled_on.desc(), WeightSample.id.desc())
        .limit(1)
    )
    direct_costs = (
        db.scalar(
            select(func.coalesce(func.sum(Expense.amount_pkr), 0)).where(
                Expense.tenant_id == principal.tenant_id,
                Expense.flock_id == flock.id,
                Expense.incurred_on <= report_date,
            )
        )
        or 0
    )
    sales_total = (
        db.scalar(
            select(func.coalesce(func.sum(Sale.amount_pkr), 0)).where(
                Sale.tenant_id == principal.tenant_id,
                Sale.flock_id == flock.id,
                Sale.sale_on <= report_date,
            )
        )
        or 0
    )
    farm_expenses = db.scalars(
        select(Expense)
        .join(ExpenseEligibleFlock, ExpenseEligibleFlock.expense_id == Expense.id)
        .where(
            Expense.tenant_id == principal.tenant_id,
            Expense.farm_id == flock.farm_id,
            Expense.scope == "farm",
            Expense.incurred_on <= report_date,
            ExpenseEligibleFlock.flock_id == flock.id,
        )
        .order_by(Expense.incurred_on, Expense.id)
    ).all()
    allocated_farm_costs = Decimal("0")
    for expense in farm_expenses:
        if expense.allocation_start is None or expense.allocation_end is None:
            raise HTTPException(409, "Farm expense allocation period is missing")
        eligible_ids = db.scalars(
            select(ExpenseEligibleFlock.flock_id).where(
                ExpenseEligibleFlock.tenant_id == principal.tenant_id,
                ExpenseEligibleFlock.expense_id == expense.id,
            )
        ).all()
        flock_days: dict[UUID, int] = {}
        total_days = 0
        for eligible_flock_id in eligible_ids:
            eligible_placed, eligible_facts, eligible_placed_on = facts_for(
                eligible_flock_id, expense.allocation_end
            )
            days = (
                calculate_bird_days_for_period(
                    eligible_placed,
                    eligible_facts,
                    eligible_placed_on,
                    expense.allocation_start,
                    expense.allocation_end,
                )
                if eligible_placed_on is not None
                else 0
            )
            flock_days[eligible_flock_id] = days
            total_days += days
        if total_days <= 0:
            raise HTTPException(
                409, "Farm expense has no eligible bird-days in its configured period"
            )
        allocated_farm_costs += allocate_farm_cost(
            expense.amount_pkr, flock_days.get(flock.id, 0), total_days
        )
    estimated: Decimal | None = None
    status = "complete"
    if price is None or average_weight is None:
        status = "missing_market_price_or_weight"
    else:
        estimated = calculate_profit(
            current_birds_alive=live_birds,
            latest_average_weight_kg=average_weight,
            entered_market_price_pkr_per_kg=price,
            recorded_sales_amount_pkr=Decimal(sales_total),
            direct_costs_pkr=Decimal(direct_costs),
            allocated_farm_costs_pkr=allocated_farm_costs,
        ).estimated_profit_pkr
    sales_total = Decimal(sales_total)
    direct_costs = Decimal(direct_costs)
    actual_profit = sales_total - direct_costs - allocated_farm_costs
    return FlockProfitRead(
        flock_id=flock.id,
        as_of=report_date,
        live_birds=live_birds,
        estimated_profit_pkr=estimated,
        actual_profit_pkr=actual_profit,
        direct_costs_pkr=direct_costs,
        allocated_farm_costs_pkr=allocated_farm_costs,
        status=status,
    )
