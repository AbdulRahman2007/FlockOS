from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.farm_access import require_farm_scope, tenant_repository
from app.core.authz import Principal, Role, get_db, require_permission
from app.models.farm_operations import Farm
from app.schemas.farm_operations import FarmCreate, FarmRead, FarmUpdate, Page
from app.services.audit import record_audit

router = APIRouter(prefix="/farms", tags=["farms"])
Db = Annotated[Session, Depends(get_db)]


def _commit(db: Session, message: str = "Farm conflicts with existing data") -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=message) from None


def _read(farm: Farm) -> FarmRead:
    return FarmRead(
        id=farm.id,
        name=farm.name,
        location=farm.location,
        timezone=farm.timezone,
        created_at=farm.created_at,
        updated_at=farm.updated_at,
    )


@router.get("", response_model=Page[FarmRead])
def list_farms(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("farm:read"))],
    search: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[FarmRead]:
    repository = tenant_repository(db, principal)
    scope_user = principal.user_id if principal.role is Role.MANAGER else None
    farms, total = repository.farms(
        search=search.strip(), limit=limit, offset=offset, user_id=scope_user
    )
    return Page(items=[_read(farm) for farm in farms], total=total, limit=limit, offset=offset)


@router.post("", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(
    data: FarmCreate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("farm:create"))],
) -> FarmRead:
    repository = tenant_repository(db, principal)
    now = datetime.now(UTC)
    farm = Farm(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        name=data.name,
        location=data.location,
        timezone=data.timezone,
        created_at=now,
        updated_at=now,
    )
    db.add(farm)
    record_audit(
        db,
        tenant_id=repository._context.tenant_id,
        actor_user_id=principal.user_id,
        action="farm.create",
        entity_type="farm",
        entity_id=str(farm.id),
        new_value=data.name,
    )
    _commit(db)
    return _read(farm)


@router.get("/{farm_id}", response_model=FarmRead)
def get_farm(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("farm:read"))],
) -> FarmRead:
    repository = tenant_repository(db, principal)
    farm = repository.farm(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    require_farm_scope(db, principal, repository, farm_id)
    return _read(farm)


@router.patch("/{farm_id}", response_model=FarmRead)
def update_farm(
    farm_id: UUID,
    data: FarmUpdate,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("farm:write"))],
) -> FarmRead:
    repository = tenant_repository(db, principal)
    require_farm_scope(db, principal, repository, farm_id)
    farm = repository.farm(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one farm field to update")
    old_value = "; ".join(f"{key}={getattr(farm, key)!r}" for key in changes)
    for key, value in changes.items():
        setattr(farm, key, value)
    farm.updated_at = datetime.now(UTC)
    record_audit(
        db,
        tenant_id=repository._context.tenant_id,
        actor_user_id=principal.user_id,
        action="farm.update",
        entity_type="farm",
        entity_id=str(farm.id),
        old_value=old_value,
        new_value="; ".join(f"{key}={value!r}" for key, value in changes.items()),
    )
    _commit(db)
    return _read(farm)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: UUID,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("farm:delete"))],
) -> Response:
    repository = tenant_repository(db, principal)
    farm = repository.farm(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    if repository.farm_has_children(farm_id):
        raise HTTPException(status_code=409, detail="Remove the farm's sheds before deleting it")
    record_audit(
        db,
        tenant_id=repository._context.tenant_id,
        actor_user_id=principal.user_id,
        action="farm.delete",
        entity_type="farm",
        entity_id=str(farm.id),
        old_value=farm.name,
    )
    db.delete(farm)
    _commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
