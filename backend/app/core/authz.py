from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.identity import AuthSession, User


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    MANAGER = "manager"
    WORKER = "worker"
    ACCOUNTANT = "accountant"


ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.SUPER_ADMIN: frozenset({"tenant:manage", "flock:reopen"}),
    Role.OWNER: frozenset(
        {
            "tenant:user_manage",
            "tenant:settings_read",
            "tenant:settings_write",
            "farm:create",
            "farm:read",
            "farm:write",
            "farm:delete",
            "shed:read",
            "shed:write",
            "shed:delete",
            "flock:read",
            "flock:write",
            "flock:delete",
            "daily:read",
            "daily:write",
            "daily:edit",
            "daily:submit",
            "weight:read",
            "weight:write",
            "weight:submit",
            "feed:read",
            "feed:write",
            "sales:read",
            "sales:write",
            "expenses:read",
            "expenses:write",
            "dashboard:read",
            "reports:read",
            "flock:close",
            "flock:reopen",
            "audit:read",
        }
    ),
    Role.MANAGER: frozenset(
        {
            "farm:read",
            "farm:write",
            "shed:read",
            "shed:write",
            "flock:read",
            "flock:write",
            "daily:read",
            "daily:write",
            "daily:edit",
            "daily:submit",
            "weight:read",
            "weight:write",
            "weight:submit",
            "feed:read",
            "feed:write",
            "sales:read",
            "sales:write",
            "expenses:read",
            "expenses:write",
            "dashboard:read",
            "reports:read",
            "flock:close",
            "audit:read",
        }
    ),
    Role.WORKER: frozenset(
        {
            "farm:read",
            "shed:read",
            "flock:read",
            "daily:read",
            "daily:own_write",
            "daily:edit",
            "daily:submit",
            "weight:read",
            "weight:own_write",
            "weight:submit",
            "dashboard:read",
        }
    ),
    Role.ACCOUNTANT: frozenset(
        {
            "farm:read",
            "shed:read",
            "flock:read",
            "daily:read",
            "weight:read",
            "feed:read",
            "sales:read",
            "sales:write",
            "expenses:read",
            "expenses:write",
            "dashboard:finance",
            "dashboard:read",
            "reports:read",
            "audit:read",
        }
    ),
}

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID | None
    role: Role


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Principal:
    unauthorized = HTTPException(status_code=401, detail="Authentication required")
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = UUID(str(claims["sub"]))
        session_id = UUID(str(claims["sid"]))
        role = Role(str(claims["role"]))
        tenant_claim = claims.get("tenant_id")
        tenant_id = UUID(str(tenant_claim)) if tenant_claim else None
    except (InvalidTokenError, ValueError, KeyError):
        raise unauthorized from None
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    session = db.scalar(
        select(AuthSession.id).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if user is None or session is None or user.role != role.value or user.tenant_id != tenant_id:
        raise unauthorized
    if (role is Role.SUPER_ADMIN) != (tenant_id is None):
        raise unauthorized
    return Principal(user_id=user.id, tenant_id=user.tenant_id, role=role)


def require_permission(permission: str) -> Callable[..., Principal]:
    def dependency(
        request: Request, principal: Annotated[Principal, Depends(authenticated_user)]
    ) -> Principal:
        if permission not in ROLE_PERMISSIONS.get(principal.role, frozenset()):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
        request.state.permission = permission
        return principal

    dependency.permission = permission  # type: ignore[attr-defined]
    return dependency


def public_operation(request: Request) -> None:
    """Explicit marker for routes intentionally available without an identity."""
    request.state.permission = "public"


public_operation.permission = "public"  # type: ignore[attr-defined]
