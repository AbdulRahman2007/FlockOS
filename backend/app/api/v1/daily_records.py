from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.farm_access import require_farm_scope, tenant_repository
from app.core.authz import Principal, Role, get_db, require_permission
from app.models.daily_records import DailyRecord
from app.models.farm_operations import Flock, Supplier
from app.repositories.base import TenantContext
from app.repositories.daily_records import DailyRepository
from app.schemas.daily_records import (
    DailyRecordCreate,
    DailyRecordList,
    DailyRecordRead,
    DailyRecordUpdate,
    FeedPurchaseCreate,
    FeedPurchaseRead,
    WeightSampleCreate,
    WeightSampleRead,
)
from app.schemas.farm_operations import Page
from app.services.daily_records import (
    DailyRecordError,
    closing_bird_counts,
    create_daily_record,
    create_feed_purchase,
    create_weight_sample,
    local_today,
    update_daily_record,
)

router = APIRouter(tags=["daily operations"])
Db = Annotated[Session, Depends(get_db)]


def _flock_or_404(
    db: Session, principal: Principal, flock_id: UUID
) -> tuple[Flock, DailyRepository]:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    repo = DailyRepository(db, TenantContext(principal.tenant_id))
    flock = repo.flock(flock_id)
    if flock is None:
        raise HTTPException(404, "Flock not found")
    farm_repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, farm_repo, flock.farm_id)
    return flock, repo


def _error(error: DailyRecordError) -> HTTPException:
    return HTTPException(error.status_code, str(error))


def _record_read(row: DailyRecord, repo: DailyRepository) -> DailyRecordRead:
    counts = closing_bird_counts(repo, row.flock_id)
    return DailyRecordRead.model_validate(row, from_attributes=True).model_copy(
        update={"closing_birds": counts[row.record_date]}
    )


@router.get("/flocks/{flock_id}/daily-records", response_model=DailyRecordList)
def list_daily_records(
    flock_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("daily:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DailyRecordList:
    flock, repo = _flock_or_404(db, principal, flock_id)
    rows, total = repo.daily_records_page(
        flock_id,
        limit=limit,
        offset=offset,
        user_id=principal.user_id if principal.role is Role.WORKER else None,
    )
    counts = closing_bird_counts(repo, flock_id)
    placements = repo.placements(flock_id)
    missing_dates = []
    if placements:
        start = min(row.placed_on for row in placements)
        end = local_today(flock, repo)
        known_dates = repo.record_dates(flock_id)
        missing_dates = [
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
            if start + timedelta(days=offset) not in known_dates
        ]
    return DailyRecordList(
        items=[
            DailyRecordRead.model_validate(row, from_attributes=True).model_copy(
                update={"closing_birds": counts[row.record_date]}
            )
            for row in rows
        ],
        missing_dates=missing_dates,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/flocks/{flock_id}/daily-records",
    response_model=DailyRecordRead,
    status_code=201,
)
def submit_daily_record(
    flock_id: UUID,
    data: DailyRecordCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("daily:submit"))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=64)],
) -> DailyRecordRead:
    flock, _ = _flock_or_404(db, principal, flock_id)
    try:
        row, _ = create_daily_record(db, principal, flock, data, idempotency_key)
    except DailyRecordError as error:
        raise _error(error) from None
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    return _record_read(row, DailyRepository(db, TenantContext(principal.tenant_id)))


@router.patch("/daily-records/{record_id}", response_model=DailyRecordRead)
def edit_daily_record(
    record_id: UUID,
    data: DailyRecordUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("daily:edit"))],
) -> DailyRecordRead:
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    repo = DailyRepository(db, TenantContext(principal.tenant_id))
    row = repo.record(record_id)
    if row is None:
        raise HTTPException(404, "Daily record not found")
    flock, _ = _flock_or_404(db, principal, row.flock_id)
    if flock.id != row.flock_id:
        raise HTTPException(404, "Daily record not found")
    try:
        updated = update_daily_record(db, principal, row, data)
    except DailyRecordError as error:
        raise _error(error) from None
    return _record_read(updated, repo)


@router.get("/flocks/{flock_id}/weight-samples", response_model=Page[WeightSampleRead])
def list_weight_samples(
    flock_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("weight:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[WeightSampleRead]:
    _, repo = _flock_or_404(db, principal, flock_id)
    samples, total = repo.weight_samples_page(
        flock_id,
        limit=limit,
        offset=offset,
        user_id=principal.user_id if principal.role is Role.WORKER else None,
    )
    return Page(
        items=[WeightSampleRead.model_validate(item, from_attributes=True) for item in samples],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/flocks/{flock_id}/weight-samples",
    response_model=WeightSampleRead,
    status_code=201,
)
def add_weight_sample(
    flock_id: UUID,
    data: WeightSampleCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("weight:submit"))],
) -> WeightSampleRead:
    flock, _ = _flock_or_404(db, principal, flock_id)
    try:
        row = create_weight_sample(
            db,
            principal,
            flock,
            data.sampled_on,
            data.sample_size,
            data.average_weight_kg,
        )
    except DailyRecordError as error:
        raise _error(error) from None
    return WeightSampleRead.model_validate(row, from_attributes=True)


@router.get("/farms/{farm_id}/feed-purchases", response_model=Page[FeedPurchaseRead])
def list_feed_purchases(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("feed:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[FeedPurchaseRead]:
    farm_repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, farm_repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    repo = DailyRepository(db, TenantContext(principal.tenant_id))
    purchases, total = repo.feed_purchases_page(farm_id, limit=limit, offset=offset)
    return Page(
        items=[FeedPurchaseRead.model_validate(item, from_attributes=True) for item in purchases],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/farms/{farm_id}/feed-purchases",
    response_model=FeedPurchaseRead,
    status_code=201,
)
def add_feed_purchase(
    farm_id: UUID,
    data: FeedPurchaseCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("feed:write"))],
) -> FeedPurchaseRead:
    farm_repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, farm_repo, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
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
    settings = farm_repo.settings()
    try:
        row = create_feed_purchase(
            db,
            principal,
            farm_id,
            data,
            settings.feed_bag_size_kg if settings is not None else None,
        )
    except DailyRecordError as error:
        raise _error(error) from None
    return FeedPurchaseRead.model_validate(row, from_attributes=True)
