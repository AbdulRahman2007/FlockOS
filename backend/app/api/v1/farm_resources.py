from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.farm_access import require_farm_scope, tenant_repository
from app.core.authz import Principal, Role, get_db, require_permission
from app.domain.farm_rules import close_flock, reopen_flock, validate_placement
from app.models.farm_operations import Flock, FlockPlacement, Shed, TenantSettings
from app.repositories.farm_operations import FarmOperationsRepository
from app.schemas.farm_operations import (
    FlockCreate,
    FlockListRead,
    FlockRead,
    FlockStatusRead,
    FlockUpdate,
    Page,
    PlacementCreate,
    PlacementRead,
    ReopenFlockRequest,
    ShedCreate,
    ShedRead,
    ShedUpdate,
    TenantSettingsRead,
    TenantSettingsUpdate,
)
from app.services.audit import record_audit

router = APIRouter(tags=["farm operations"])
Db = Annotated[Session, Depends(get_db)]


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        reason = str(getattr(error, "orig", ""))
        if "capacity" in reason.lower():
            detail = "The placement would exceed shed capacity"
        elif "active" in reason.lower():
            detail = "This shed already has an active flock"
        else:
            detail = "The change conflicts with existing farm records"
        raise HTTPException(status_code=409, detail=detail) from None


def _placement_read(row: FlockPlacement) -> PlacementRead:
    return PlacementRead(
        id=row.id,
        placed_on=row.placed_on,
        bird_count=row.bird_count,
        chick_source=row.chick_source,
        average_weight_kg=row.average_weight_kg,
    )


def _flock_read(repo: FarmOperationsRepository, row: Flock, birds: int | None = None) -> FlockRead:
    count = repo.placed_birds(row.id) if birds is None else birds
    return FlockRead(
        id=row.id,
        farm_id=row.farm_id,
        shed_id=row.shed_id,
        name=row.name,
        status=row.status,
        locked=row.status == "closed",
        placed_birds=count,
        placements=[_placement_read(item) for item in repo.placements(row.id)],
        closed_at=row.closed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/farms/{farm_id}/sheds", response_model=Page[ShedRead])
def list_sheds(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("shed:read"))],
    search: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ShedRead]:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    rows, total = repo.sheds(farm_id, search=search.strip(), limit=limit, offset=offset)
    return Page(
        items=[ShedRead.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/farms/{farm_id}/sheds", response_model=ShedRead, status_code=201)
def create_shed(
    farm_id: UUID,
    data: ShedCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("shed:write"))],
) -> ShedRead:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, farm_id)
    now = datetime.now(UTC)
    row = Shed(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        name=data.name,
        capacity_birds=data.capacity_birds,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="shed.create",
        entity_type="shed",
        entity_id=str(row.id),
        new_value=data.name,
    )
    _commit(db)
    return ShedRead.model_validate(row, from_attributes=True)


@router.patch("/sheds/{shed_id}", response_model=ShedRead)
def update_shed(
    shed_id: UUID,
    data: ShedUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("shed:write"))],
) -> ShedRead:
    repo = tenant_repository(db, principal)
    row = repo.shed(shed_id)
    if row is None:
        raise HTTPException(404, "Shed not found")
    require_farm_scope(db, principal, repo, row.farm_id)
    values = data.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(422, "Provide at least one shed field to update")
    old = ", ".join(f"{key}={getattr(row, key)!r}" for key in values)
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="shed.update",
        entity_type="shed",
        entity_id=str(row.id),
        old_value=old,
        new_value=str(values),
    )
    _commit(db)
    return ShedRead.model_validate(row, from_attributes=True)


@router.delete("/sheds/{shed_id}", status_code=204)
def delete_shed(
    shed_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("shed:delete"))],
) -> Response:
    repo = tenant_repository(db, principal)
    row = repo.shed(shed_id)
    if row is None:
        raise HTTPException(404, "Shed not found")
    require_farm_scope(db, principal, repo, row.farm_id)
    if repo.shed_has_flocks(shed_id):
        raise HTTPException(409, "Move or remove flocks before deleting this shed")
    db.delete(row)
    _commit(db)
    return Response(status_code=204)


@router.get("/flocks", response_model=Page[FlockListRead])
def list_flocks(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:read"))],
    search: Annotated[str, Query(max_length=120)] = "",
    farm_id: UUID | None = None,
    flock_status: Annotated[str | None, Query(alias="status", pattern="^(active|closed)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[FlockListRead]:
    repo = tenant_repository(db, principal)
    if farm_id is not None:
        require_farm_scope(db, principal, repo, farm_id)
    scope_user = principal.user_id if principal.role is Role.MANAGER else None
    rows, total = repo.flocks(
        search=search.strip(),
        status=flock_status,
        farm_id=farm_id,
        user_id=scope_user,
        limit=limit,
        offset=offset,
    )
    items = [
        FlockListRead(
            id=row.id,
            farm_id=row.farm_id,
            shed_id=row.shed_id,
            name=row.name,
            status=row.status,
            locked=row.status == "closed",
            placed_birds=birds,
            closed_at=row.closed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row, birds in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/flocks", response_model=FlockRead, status_code=201)
def create_flock(
    data: FlockCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:write"))],
) -> FlockRead:
    repo = tenant_repository(db, principal)
    require_farm_scope(db, principal, repo, data.farm_id)
    shed = repo.shed(data.shed_id)
    if shed is None or shed.farm_id != data.farm_id:
        raise HTTPException(404, "Shed not found in this farm")
    if data.placement is not None:
        try:
            validate_placement(data.placement.bird_count, shed.capacity_birds)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
    now = datetime.now(UTC)
    flock = Flock(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=data.farm_id,
        shed_id=data.shed_id,
        name=data.name,
        status="active",
        closed_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(flock)
    if data.placement is not None:
        p = data.placement
        db.add(
            FlockPlacement(
                id=uuid4(),
                tenant_id=principal.tenant_id,
                flock_id=flock.id,
                placed_on=p.placed_on,
                bird_count=p.bird_count,
                chick_source=p.chick_source,
                average_weight_kg=p.average_weight_kg,
                created_by=principal.user_id,
                created_at=now,
            )
        )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="flock.create",
        entity_type="flock",
        entity_id=str(flock.id),
        new_value=data.name,
    )
    _commit(db)
    return _flock_read(repo, flock)


@router.get("/flocks/{flock_id}", response_model=FlockRead)
def get_flock(
    flock_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:read"))],
) -> FlockRead:
    repo = tenant_repository(db, principal)
    flock = repo.flock(flock_id)
    if flock is None:
        raise HTTPException(404, "Flock not found")
    require_farm_scope(db, principal, repo, flock.farm_id)
    return _flock_read(repo, flock)


@router.patch("/flocks/{flock_id}", response_model=FlockRead)
def update_flock(
    flock_id: UUID,
    data: FlockUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:write"))],
) -> FlockRead:
    repo = tenant_repository(db, principal)
    flock = repo.flock(flock_id)
    if flock is None:
        raise HTTPException(404, "Flock not found")
    require_farm_scope(db, principal, repo, flock.farm_id)
    if flock.status != "active":
        raise HTTPException(423, "Closed flocks are locked")
    old = flock.name
    flock.name = data.name
    flock.updated_at = datetime.now(UTC)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="flock.update",
        entity_type="flock",
        entity_id=str(flock.id),
        old_value=old,
        new_value=data.name,
    )
    _commit(db)
    return _flock_read(repo, flock)


@router.delete("/flocks/{flock_id}", status_code=204)
def delete_flock(
    flock_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:delete"))],
) -> Response:
    repo = tenant_repository(db, principal)
    flock = repo.flock(flock_id)
    if flock is None:
        raise HTTPException(404, "Flock not found")
    require_farm_scope(db, principal, repo, flock.farm_id)
    if repo.flock_has_activity(flock_id):
        raise HTTPException(
            409,
            "Placed flocks cannot be deleted. Close the flock to retain its records.",
        )
    db.delete(flock)
    _commit(db)
    return Response(status_code=204)


@router.post("/flocks/{flock_id}/placements", response_model=PlacementRead, status_code=201)
def add_placement(
    flock_id: UUID,
    data: PlacementCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:write"))],
) -> PlacementRead:
    repo = tenant_repository(db, principal)
    flock = repo.flock(flock_id)
    if flock is None:
        raise HTTPException(404, "Flock not found")
    require_farm_scope(db, principal, repo, flock.farm_id)
    if flock.status != "active":
        raise HTTPException(423, "Closed flocks are locked")
    if repo.placement_exists_on(flock_id, data.placed_on):
        raise HTTPException(409, "A placement already exists for this flock and date")
    shed = repo.shed(flock.shed_id)
    assert shed is not None
    try:
        validate_placement(data.bird_count, shed.capacity_birds, repo.placed_birds(flock_id))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    row = FlockPlacement(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        flock_id=flock.id,
        placed_on=data.placed_on,
        bird_count=data.bird_count,
        chick_source=data.chick_source,
        average_weight_kg=data.average_weight_kg,
        created_by=principal.user_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    _commit(db)
    return _placement_read(row)


@router.post("/flocks/{flock_id}/close", response_model=FlockRead)
def close_flock_endpoint(
    flock_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:close"))],
) -> FlockRead:
    repo = tenant_repository(db, principal)
    flock = repo.flock(flock_id)
    if flock is None:
        raise HTTPException(404, "Flock not found")
    require_farm_scope(db, principal, repo, flock.farm_id)
    try:
        status_change = close_flock(flock.status)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    flock.status, flock.closed_at, flock.updated_at = (
        status_change.status,
        status_change.closed_at,
        datetime.now(UTC),
    )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="flock.close",
        entity_type="flock",
        entity_id=str(flock.id),
        old_value="active",
        new_value="closed",
    )
    _commit(db)
    return _flock_read(repo, flock)


@router.post("/flocks/{flock_id}/reopen", response_model=FlockStatusRead)
def reopen_flock_endpoint(
    flock_id: UUID,
    data: ReopenFlockRequest,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("flock:reopen"))],
) -> FlockStatusRead:
    tenant_id: UUID | None
    if principal.role is Role.SUPER_ADMIN:
        flock = db.scalar(select(Flock).where(Flock.id == flock_id).with_for_update())
        if flock is None:
            raise HTTPException(404, "Flock not found")
        tenant_id = flock.tenant_id
    else:
        tenant_repo = tenant_repository(db, principal)
        flock = tenant_repo.flock(flock_id)
        tenant_id = principal.tenant_id
    if flock is None:
        raise HTTPException(404, "Flock not found")
    try:
        status_change = reopen_flock(flock.status)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    flock.status, flock.closed_at, flock.updated_at = (
        status_change.status,
        status_change.closed_at,
        datetime.now(UTC),
    )
    record_audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=principal.user_id,
        action="flock.reopen",
        entity_type="flock",
        entity_id=str(flock.id),
        old_value="closed",
        new_value=f"active; reason={data.reason}",
    )
    _commit(db)
    return FlockStatusRead(flock_id=flock.id, status=flock.status, locked=flock.status == "closed")


@router.get("/settings", response_model=TenantSettingsRead)
def get_settings(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("tenant:settings_read"))],
) -> TenantSettingsRead:
    repo = tenant_repository(db, principal)
    row = repo.settings()
    if row is None:
        return TenantSettingsRead(
            feed_bag_size_kg=None,
            target_mortality_percent=None,
            target_fcr=None,
            manager_daily_window_days=7,
            worker_daily_window_days=1,
            updated_at=None,
        )
    return TenantSettingsRead.model_validate(row, from_attributes=True)


@router.put("/settings", response_model=TenantSettingsRead)
def update_settings(
    data: TenantSettingsUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("tenant:settings_write"))],
) -> TenantSettingsRead:
    repo = tenant_repository(db, principal)
    row = repo.settings()
    now = datetime.now(UTC)
    values = data.model_dump()
    if row is None:
        row = TenantSettings(
            tenant_id=principal.tenant_id, updated_by=principal.user_id, updated_at=now, **values
        )
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_by, row.updated_at = principal.user_id, now
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="tenant.settings.update",
        entity_type="tenant_settings",
        entity_id=str(principal.tenant_id),
        new_value=str(values),
    )
    _commit(db)
    return TenantSettingsRead.model_validate(row, from_attributes=True)
