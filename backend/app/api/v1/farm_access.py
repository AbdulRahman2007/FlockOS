from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authz import Principal, Role
from app.models.identity import FarmAssignment
from app.repositories.base import TenantContext
from app.repositories.farm_operations import FarmOperationsRepository


def tenant_repository(db: Session, principal: Principal) -> FarmOperationsRepository:
    if principal.tenant_id is None:
        raise HTTPException(status_code=403, detail="Not permitted")
    return FarmOperationsRepository(db, TenantContext(principal.tenant_id))


def require_farm_scope(
    db: Session,
    principal: Principal,
    repository: FarmOperationsRepository,
    farm_id: UUID,
) -> None:
    farm = repository.farm(farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    if principal.role is Role.MANAGER:
        assigned = db.scalar(
            select(FarmAssignment.id).where(
                FarmAssignment.tenant_id == principal.tenant_id,
                FarmAssignment.user_id == principal.user_id,
                FarmAssignment.farm_id == farm_id,
            )
        )
        if assigned is None:
            raise HTTPException(status_code=404, detail="Farm not found")
