from datetime import date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.farm_access import require_farm_scope, tenant_repository
from app.core.authz import Principal, get_db, require_permission
from app.repositories.base import TenantContext
from app.repositories.feed_stock import FeedStockRepository
from app.schemas.feed_stock import (
    FeedStockEventCreate,
    FeedStockEventItem,
    FeedStockEventPage,
    FeedStockEventRead,
    FeedStockSnapshotRead,
)
from app.services.feed_stock import (
    FeedStockError,
    create_feed_stock_event,
    feed_stock_snapshot,
)

router = APIRouter(tags=["feed stock"])
Db = Annotated[Session, Depends(get_db)]


def _farm_scope(db: Session, principal: Principal, farm_id: UUID):
    farm_repository = tenant_repository(db, principal)
    require_farm_scope(db, principal, farm_repository, farm_id)
    farm = farm_repository.farm(farm_id)
    if farm is None:
        raise HTTPException(404, "Farm not found")
    return farm


@router.get("/farms/{farm_id}/feed-stock", response_model=FeedStockSnapshotRead)
def read_feed_stock(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("feed:read"))],
    as_of: Annotated[date | None, Query()] = None,
) -> FeedStockSnapshotRead:
    farm = _farm_scope(db, principal, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    local_date = as_of or datetime.now(ZoneInfo(farm.timezone)).date()
    return feed_stock_snapshot(
        db, tenant_id=principal.tenant_id, farm_id=farm_id, as_of=local_date
    )


@router.get("/farms/{farm_id}/feed-stock/events", response_model=FeedStockEventPage)
def list_feed_stock_events(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("feed:read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FeedStockEventPage:
    _farm_scope(db, principal, farm_id)
    if principal.tenant_id is None:
        raise HTTPException(403, "Not permitted")
    repo = FeedStockRepository(db, TenantContext(principal.tenant_id))
    items, total = repo.movement_page(farm_id, limit=limit, offset=offset)
    return FeedStockEventPage(
        items=[FeedStockEventItem.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/farms/{farm_id}/feed-stock/events",
    response_model=FeedStockEventRead,
    status_code=201,
)
def add_feed_stock_event(
    farm_id: UUID,
    data: FeedStockEventCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("feed:write"))],
) -> FeedStockEventRead:
    _farm_scope(db, principal, farm_id)
    try:
        row = create_feed_stock_event(db, principal, farm_id, data)
    except FeedStockError as error:
        raise HTTPException(error.status_code, str(error)) from None
    return FeedStockEventRead.model_validate(row, from_attributes=True)
