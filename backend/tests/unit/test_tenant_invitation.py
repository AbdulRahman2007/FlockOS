from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.authz import Role, get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models.identity import AuditLog, AuthSession, Invitation, Tenant, User


def test_super_admin_can_create_tenant_and_owner_invitation() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    user_id, session_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    session.add(
        User(
            id=user_id,
            tenant_id=None,
            email="platform-admin@example.com",
            full_name="Platform Admin",
            password_hash="unused",
            role=Role.SUPER_ADMIN.value,
            is_active=True,
            created_at=now,
        )
    )
    session.flush()
    session.add(
        AuthSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash="a" * 64,
            expires_at=now + timedelta(days=1),
            created_at=now,
        )
    )
    session.commit()
    token = create_access_token(
        user_id=str(user_id),
        role=Role.SUPER_ADMIN.value,
        tenant_id=None,
        session_id=str(session_id),
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/tenants",
                json={
                    "tenant_name": "Invitation Test Tenant",
                    "owner_email": "owner@example.com",
                    "owner_name": "Tenant Owner",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 201
        invitation = session.scalar(select(Invitation))
        tenant = session.scalar(select(Tenant))
        audit = session.scalar(select(AuditLog).where(AuditLog.action == "tenant.create"))
        assert invitation is not None
        assert tenant is not None
        assert audit is not None
        assert invitation.tenant_id == tenant.id == audit.tenant_id
        assert invitation.email == "owner@example.com"
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
