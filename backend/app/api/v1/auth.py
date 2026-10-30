from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.authz import Principal, Role, get_db, public_operation, require_permission
from app.core.config import get_settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    new_opaque_token,
    token_digest,
    verify_password,
)
from app.models.identity import AuthSession, Invitation, LoginAttempt, Tenant, User
from app.repositories.base import TenantContext, TenantRepository
from app.schemas.auth import (
    AcceptInviteRequest,
    ChangeRoleRequest,
    CreateTenantRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    TenantSummary,
    TokenResponse,
    UserSummary,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]


def _token_response(user: User, session_id: UUID) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(
            user_id=str(user.id),
            role=user.role,
            tenant_id=str(user.tenant_id) if user.tenant_id else None,
            session_id=str(session_id),
        ),
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(public_operation)])
def login(data: LoginRequest, request: Request, response: Response, db: Db) -> TokenResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    window_seconds = max(1, settings.login_window_seconds)
    window = datetime.fromtimestamp(int(now.timestamp()) // window_seconds * window_seconds, UTC)
    bucket = sha256(
        f"{request.client.host if request.client else 'unknown'}:{data.email.lower()}".encode()
    ).hexdigest()
    attempt = db.scalar(
        select(LoginAttempt).where(
            LoginAttempt.bucket_key == bucket, LoginAttempt.window_start == window
        )
    )
    if attempt and attempt.attempts >= settings.login_max_attempts:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    user = db.scalar(select(User).where(User.email == data.email.lower(), User.is_active.is_(True)))
    encoded_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(data.password, encoded_hash)
    if user is None or not password_matches:
        statement = (
            insert(LoginAttempt)
            .values(id=uuid4(), bucket_key=bucket, window_start=window, attempts=1)
            .on_conflict_do_update(
                index_elements=["bucket_key", "window_start"],
                set_={"attempts": LoginAttempt.attempts + 1},
            )
        )
        db.execute(statement)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    db.execute(delete(LoginAttempt).where(LoginAttempt.bucket_key == bucket))
    refresh_token = new_opaque_token()
    session = AuthSession(
        id=uuid4(),
        user_id=user.id,
        refresh_token_hash=token_digest(refresh_token),
        expires_at=now + timedelta(days=settings.refresh_token_days),
        created_at=now,
    )
    db.add(session)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.login",
        entity_type="auth_session",
        entity_id=str(session.id),
    )
    db.commit()
    response.set_cookie(
        "pouktry_refresh",
        refresh_token,
        httponly=True,
        secure=settings.app_environment == "production",
        samesite="lax",
        max_age=settings.refresh_token_days * 86400,
        path="/api/v1/auth",
    )
    return _token_response(user, session.id)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(public_operation)])
def refresh(request: Request, response: Response, db: Db) -> TokenResponse:
    raw = request.cookies.get("pouktry_refresh")
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required")
    now = datetime.now(UTC)
    current = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_digest(raw))
        .with_for_update()
    )
    if current is None or current.revoked_at is not None or current.expires_at <= now:
        if current is not None and current.revoked_at is not None:
            db.query(AuthSession).filter(AuthSession.user_id == current.user_id).update(
                {AuthSession.revoked_at: now}
            )
            user = db.get(User, current.user_id)
            record_audit(
                db,
                tenant_id=user.tenant_id if user else None,
                actor_user_id=current.user_id,
                action="auth.refresh_replay",
                entity_type="auth_session",
                entity_id=str(current.id),
            )
            db.commit()
        response.delete_cookie("pouktry_refresh", path="/api/v1/auth")
        raise HTTPException(status_code=401, detail="Authentication required")
    user = db.get(User, current.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication required")
    current.revoked_at = now
    new_refresh = new_opaque_token()
    rotated_session = AuthSession(
        id=uuid4(),
        user_id=user.id,
        refresh_token_hash=token_digest(new_refresh),
        expires_at=now + timedelta(days=get_settings().refresh_token_days),
        created_at=now,
    )
    db.add(rotated_session)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.refresh",
        entity_type="auth_session",
        entity_id=str(current.id),
    )
    db.commit()
    response.set_cookie(
        "pouktry_refresh",
        new_refresh,
        httponly=True,
        secure=get_settings().app_environment == "production",
        samesite="lax",
        max_age=get_settings().refresh_token_days * 86400,
        path="/api/v1/auth",
    )
    return _token_response(user, rotated_session.id)


@router.post("/logout", status_code=204, dependencies=[Depends(public_operation)])
def logout(
    request: Request,
    response: Response,
    db: Db,
) -> Response:
    raw = request.cookies.get("pouktry_refresh")
    if raw:
        current = db.scalar(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_digest(raw))
        )
        if current and current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
            user = db.get(User, current.user_id)
            record_audit(
                db,
                tenant_id=user.tenant_id if user else None,
                actor_user_id=current.user_id,
                action="auth.logout",
                entity_type="auth_session",
                entity_id=str(current.id),
            )
            db.commit()
    response.delete_cookie("pouktry_refresh", path="/api/v1/auth")
    return response


@router.post("/invitations", response_model=InviteResponse, status_code=201)
def create_invitation(
    data: InviteRequest,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("tenant:user_manage"))],
) -> InviteResponse:
    if principal.tenant_id is None:
        raise HTTPException(status_code=403, detail="Not permitted")
    try:
        role = Role(data.role)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid role") from None
    if role in {Role.SUPER_ADMIN, Role.OWNER}:
        raise HTTPException(status_code=403, detail="Not permitted")
    if db.scalar(select(User.id).where(User.email == data.email.lower())):
        raise HTTPException(status_code=409, detail="Account already exists")
    token = new_opaque_token()
    invitation = Invitation(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        email=data.email.lower(),
        full_name=data.full_name,
        role=role.value,
        token_hash=token_digest(token),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        created_by=principal.user_id,
    )
    db.add(invitation)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="identity.invite",
        entity_type="invitation",
        entity_id=str(invitation.id),
    )
    db.commit()
    # Token delivery is a deployment integration; returning it supports local setup only.
    return InviteResponse(invitation_id=str(invitation.id), invite_token=token, expires_in=604800)


@router.post("/tenants", response_model=InviteResponse, status_code=201)
def create_tenant(
    data: CreateTenantRequest,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("tenant:manage"))],
) -> InviteResponse:
    if db.scalar(select(User.id).where(User.email == data.owner_email.lower())):
        raise HTTPException(status_code=409, detail="Account already exists")
    now = datetime.now(UTC)
    tenant = Tenant(id=uuid4(), name=data.tenant_name, plan=None, user_limit=None, created_at=now)
    token = new_opaque_token()
    invitation = Invitation(
        id=uuid4(),
        tenant_id=tenant.id,
        email=data.owner_email.lower(),
        full_name=data.owner_name,
        role=Role.OWNER.value,
        token_hash=token_digest(token),
        expires_at=now + timedelta(days=7),
        created_by=principal.user_id,
    )
    db.add(tenant)
    db.flush()
    db.add(invitation)
    db.flush()
    record_audit(
        db,
        tenant_id=tenant.id,
        actor_user_id=principal.user_id,
        action="tenant.create",
        entity_type="tenant",
        entity_id=str(tenant.id),
        new_value=tenant.name,
    )
    db.commit()
    return InviteResponse(invitation_id=str(invitation.id), invite_token=token, expires_in=604800)


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants(
    db: Db,
    _principal: Annotated[Principal, Depends(require_permission("tenant:manage"))],
) -> list[TenantSummary]:
    tenants = db.scalars(select(Tenant).order_by(Tenant.name)).all()
    return [TenantSummary(id=str(tenant.id), name=tenant.name) for tenant in tenants]


@router.get("/users", response_model=list[UserSummary])
def list_users(
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("tenant:user_manage"))],
) -> list[UserSummary]:
    if principal.tenant_id is None:
        raise HTTPException(status_code=403, detail="Not permitted")
    repository = TenantRepository(db, TenantContext(principal.tenant_id))
    users = db.scalars(repository.scoped(User).order_by(User.email)).all()
    return [
        UserSummary(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )
        for user in users
    ]


@router.patch("/users/{user_id}/role", response_model=UserSummary)
def change_user_role(
    user_id: str,
    data: ChangeRoleRequest,
    db: Db,
    principal: Annotated[Principal, Depends(require_permission("tenant:user_manage"))],
) -> UserSummary:
    if principal.tenant_id is None:
        raise HTTPException(status_code=403, detail="Not permitted")
    try:
        target_id = UUID(user_id)
        new_role = Role(data.role)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid user or role") from None
    if new_role in {Role.SUPER_ADMIN, Role.OWNER}:
        raise HTTPException(status_code=422, detail="Role cannot be assigned")
    target = db.scalar(
        select(User)
        .where(User.id == target_id, User.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == Role.OWNER.value:
        raise HTTPException(status_code=403, detail="Owner role cannot be changed here")
    old_role = target.role
    target.role = new_role.value
    db.query(AuthSession).filter(
        AuthSession.user_id == target.id, AuthSession.revoked_at.is_(None)
    ).update({AuthSession.revoked_at: datetime.now(UTC)})
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="identity.role_change",
        entity_type="user",
        entity_id=str(target.id),
        old_value=old_role,
        new_value=new_role.value,
    )
    db.commit()
    return UserSummary(
        id=str(target.id),
        email=target.email,
        full_name=target.full_name,
        role=target.role,
        is_active=target.is_active,
    )


@router.post("/invitations/accept", status_code=204, dependencies=[Depends(public_operation)])
def accept_invitation(data: AcceptInviteRequest, db: Db) -> Response:
    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == token_digest(data.token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if invitation is None or invitation.accepted_at is not None or invitation.expires_at <= now:
        raise HTTPException(status_code=400, detail="Invitation is invalid or expired")
    if db.scalar(select(User.id).where(User.email == invitation.email)):
        raise HTTPException(status_code=409, detail="Account already exists")
    user = User(
        id=uuid4(),
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        full_name=invitation.full_name,
        password_hash=hash_password(data.password),
        role=invitation.role,
        is_active=True,
        created_at=now,
    )
    invitation.accepted_at = now
    db.add(user)
    record_audit(
        db,
        tenant_id=invitation.tenant_id,
        actor_user_id=None,
        action="identity.invitation.accept",
        entity_type="user",
        entity_id=str(user.id),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
