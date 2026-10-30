from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.authz import ROLE_PERMISSIONS, Principal, Role, get_db, require_permission
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models.identity import AuthSession, Tenant, User


def _api_routes(routes: object) -> list[APIRoute]:
    if not isinstance(routes, (list, tuple)):
        return []
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
            continue
        for attribute in ("routes", "router", "original_router"):
            nested = getattr(route, attribute, None)
            if isinstance(nested, (list, tuple)):
                found.extend(_api_routes(nested))
            elif nested is not None:
                found.extend(_api_routes(getattr(nested, "routes", None)))
    return found


def _route_permission(route: APIRoute) -> str | None:
    for dependency in route.dependant.dependencies:
        marker = getattr(dependency.call, "permission", None)
        if marker:
            return str(marker)
    return None


def test_every_api_route_declares_explicit_permission_or_public_access() -> None:
    routes = _api_routes(app.routes)
    assert routes
    missing = [
        f"{','.join(sorted(route.methods or []))} {route.path}"
        for route in routes
        if _route_permission(route) is None
    ]
    assert missing == []


def test_authorization_matrix_covers_every_api_method_for_every_role() -> None:
    routes = _api_routes(app.routes)
    expected = {
        ("/health", "GET"): set(Role),
        ("/ready", "GET"): set(Role),
        ("/api/v1/auth/login", "POST"): set(Role),
        ("/api/v1/auth/refresh", "POST"): set(Role),
        ("/api/v1/auth/logout", "POST"): set(Role),
        ("/api/v1/auth/invitations", "POST"): {Role.OWNER},
        ("/api/v1/auth/invitations/accept", "POST"): set(Role),
        ("/api/v1/auth/tenants", "POST"): {Role.SUPER_ADMIN},
        ("/api/v1/auth/tenants", "GET"): {Role.SUPER_ADMIN},
        ("/api/v1/auth/users", "GET"): {Role.OWNER},
        ("/api/v1/auth/users/{user_id}/role", "PATCH"): {Role.OWNER},
        ("/api/v1/farms", "GET"): {Role.OWNER, Role.MANAGER, Role.WORKER, Role.ACCOUNTANT},
        ("/api/v1/farms", "POST"): {Role.OWNER},
        ("/api/v1/farms/{farm_id}", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/farms/{farm_id}", "PATCH"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/farms/{farm_id}", "DELETE"): {Role.OWNER},
        ("/api/v1/farms/{farm_id}/sheds", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/farms/{farm_id}/sheds", "POST"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/sheds/{shed_id}", "PATCH"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/sheds/{shed_id}", "DELETE"): {Role.OWNER},
        ("/api/v1/flocks", "GET"): {Role.OWNER, Role.MANAGER, Role.WORKER, Role.ACCOUNTANT},
        ("/api/v1/flocks", "POST"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/flocks/{flock_id}", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/flocks/{flock_id}", "PATCH"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/flocks/{flock_id}", "DELETE"): {Role.OWNER},
        ("/api/v1/flocks/{flock_id}/placements", "POST"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/flocks/{flock_id}/close", "POST"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/flocks/{flock_id}/reopen", "POST"): {Role.OWNER, Role.SUPER_ADMIN},
        ("/api/v1/flocks/{flock_id}/daily-records", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/flocks/{flock_id}/daily-records", "POST"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
        },
        ("/api/v1/daily-records/{record_id}", "PATCH"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
        },
        ("/api/v1/flocks/{flock_id}/weight-samples", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/flocks/{flock_id}/weight-samples", "POST"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
        },
        ("/api/v1/farms/{farm_id}/feed-purchases", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/farms/{farm_id}/feed-purchases", "POST"): {Role.OWNER, Role.MANAGER},
        ("/api/v1/farms/{farm_id}/market-prices", "POST"): {
            Role.OWNER,
            Role.MANAGER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/dashboard", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.WORKER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/farms/{farm_id}/direct-costs", "POST"): {
            Role.OWNER,
            Role.MANAGER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/buyers", "POST"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/buyers", "GET"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/suppliers", "POST"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/suppliers", "GET"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/farms/{farm_id}/sales", "GET"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/farms/{farm_id}/expenses", "GET"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/farms/{farm_id}/expenses", "POST"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/expenses/{expense_id}", "PATCH"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/farms/{farm_id}/sales", "POST"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/sales/{sale_id}/payments", "POST"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/sales/{sale_id}", "PATCH"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/buyers/outstanding", "GET"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/flocks/{flock_id}/profit", "GET"): {Role.OWNER, Role.MANAGER, Role.ACCOUNTANT},
        ("/api/v1/reports/{report_type}", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/reports/{report_type}/export.csv", "GET"): {
            Role.OWNER,
            Role.MANAGER,
            Role.ACCOUNTANT,
        },
        ("/api/v1/settings", "GET"): {Role.OWNER},
        ("/api/v1/settings", "PUT"): {Role.OWNER},
    }
    observed: set[tuple[str, str]] = set()
    for route in routes:
        permission = _route_permission(route)
        assert permission is not None
        for method in route.methods or set():
            path = route.path
            if not path.startswith(("/api/v1/", "/health", "/ready")):
                path = f"/api/v1{path}"
            key = (path, method)
            observed.add(key)
            assert key in expected, f"Add {key} to the authorization matrix test"
            for role in Role:
                should_allow = role in expected[key]
                if permission == "public":
                    allowed = True
                else:
                    dependency = require_permission(permission)
                    request = SimpleNamespace(state=SimpleNamespace())
                    principal = Principal(user_id=uuid4(), tenant_id=uuid4(), role=role)
                    try:
                        dependency(request=request, principal=principal)  # type: ignore[call-arg]
                        allowed = True
                    except HTTPException as error:
                        assert error.status_code == 403
                        allowed = False
                assert allowed == should_allow, f"{role.value} access mismatch for {key}"
                if should_allow and permission != "public":
                    assert request.state.permission == permission
                assert (permission == "public" or permission in ROLE_PERMISSIONS[role]) == (
                    should_allow
                ), f"Permission declaration mismatch for {role.value} on {key}"
    assert observed == set(expected)


def test_workers_have_no_finance_or_user_management_permissions() -> None:
    assert not any(
        permission.startswith(("sales:", "expenses:", "tenant:user"))
        for permission in ROLE_PERMISSIONS[Role.WORKER]
    )


def test_super_admin_has_no_tenant_business_data_permissions() -> None:
    assert ROLE_PERMISSIONS[Role.SUPER_ADMIN] == frozenset({"tenant:manage", "flock:reopen"})


def test_tenant_user_endpoint_never_returns_another_tenants_users() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    tenant_a_id, tenant_b_id = uuid4(), uuid4()
    owner_id, owner_session_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    tenant_a = Tenant(id=tenant_a_id, name="Tenant A", created_at=now)
    tenant_b = Tenant(id=tenant_b_id, name="Tenant B", created_at=now)
    owner = User(
        id=owner_id,
        tenant_id=tenant_a_id,
        email="owner-a@example.test",
        full_name="Owner A",
        password_hash="unused",
        role=Role.OWNER.value,
        is_active=True,
        created_at=now,
    )
    local_user = User(
        id=uuid4(),
        tenant_id=tenant_a_id,
        email="worker-a@example.test",
        full_name="Worker A",
        password_hash="unused",
        role=Role.WORKER.value,
        is_active=True,
        created_at=now,
    )
    foreign_user = User(
        id=uuid4(),
        tenant_id=tenant_b_id,
        email="owner-b@example.test",
        full_name="Owner B",
        password_hash="unused",
        role=Role.OWNER.value,
        is_active=True,
        created_at=now,
    )
    with Session(engine) as session:
        session.add_all(
            [
                tenant_a,
                tenant_b,
                owner,
                local_user,
                foreign_user,
                AuthSession(
                    id=owner_session_id,
                    user_id=owner_id,
                    refresh_token_hash="a" * 64,
                    expires_at=now + timedelta(days=1),
                    created_at=now,
                ),
            ]
        )
        session.commit()
        access_token = create_access_token(
            user_id=str(owner_id),
            role=Role.OWNER.value,
            tenant_id=str(tenant_a_id),
            session_id=str(owner_session_id),
        )

        def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/auth/users", headers={"Authorization": f"Bearer {access_token}"}
                )
        finally:
            app.dependency_overrides.pop(get_db, None)
    engine.dispose()

    assert response.status_code == 200
    assert {entry["email"] for entry in response.json()} == {
        "owner-a@example.test",
        "worker-a@example.test",
    }
    assert "owner-b@example.test" not in {entry["email"] for entry in response.json()}
