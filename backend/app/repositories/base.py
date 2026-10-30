from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID):
            raise ValueError("A valid tenant id is required")


class TenantRepository:
    """Tenant-scoped repository base; construction requires verified tenant context."""

    def __init__(self, session: Session, context: TenantContext) -> None:
        self._session = session
        self._context = context

    def scoped[ModelT](self, model: type[ModelT]) -> Select[ModelT]:
        if not hasattr(model, "tenant_id"):
            raise TypeError("Tenant repositories can only query tenant-owned models")
        return select(model).where(model.tenant_id == self._context.tenant_id)  # type: ignore[attr-defined]
