from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.authz import Role, get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models.farm_operations import Buyer
from app.models.identity import AuditLog, AuthSession, Tenant, User


def test_owner_creates_farm_shed_and_flock_through_api() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    tenant_id, user_id, session_id = uuid4(), uuid4(), uuid4()
    other_tenant_id, other_user_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    session = Session(engine)
    session.add_all(
        [
            Tenant(id=tenant_id, name="Farm API tenant", created_at=now),
            Tenant(id=other_tenant_id, name="Other tenant", created_at=now),
            User(
                id=user_id,
                tenant_id=tenant_id,
                email="farm-owner@example.test",
                full_name="Farm Owner",
                password_hash="unused",
                role=Role.OWNER.value,
                is_active=True,
                created_at=now,
            ),
            User(
                id=other_user_id,
                tenant_id=other_tenant_id,
                email="other-owner@example.test",
                full_name="Other Owner",
                password_hash="unused",
                role=Role.OWNER.value,
                is_active=True,
                created_at=now,
            ),
            AuthSession(
                id=session_id,
                user_id=user_id,
                refresh_token_hash="a" * 64,
                expires_at=now + timedelta(days=1),
                created_at=now,
            ),
        ]
    )
    foreign_buyer_id = uuid4()
    session.add(
        Buyer(
            id=foreign_buyer_id,
            tenant_id=other_tenant_id,
            name="Foreign buyer",
            created_by=other_user_id,
            created_at=now,
        )
    )
    session.commit()
    token = create_access_token(
        user_id=str(user_id),
        role=Role.OWNER.value,
        tenant_id=str(tenant_id),
        session_id=str(session_id),
    )

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {token}"}
            farm_response = client.post(
                "/api/v1/farms",
                json={"name": "Unit Farm", "timezone": "Asia/Karachi"},
                headers=headers,
            )
            assert farm_response.status_code == 201
            farm_id = farm_response.json()["id"]

            shed_response = client.post(
                f"/api/v1/farms/{farm_id}/sheds",
                json={"name": "Shed A", "capacity_birds": 50},
                headers=headers,
            )
            assert shed_response.status_code == 201
            shed_id = shed_response.json()["id"]

            flock_response = client.post(
                "/api/v1/flocks",
                json={
                    "farm_id": farm_id,
                    "shed_id": shed_id,
                    "name": "Flock A",
                    "placement": {
                        "placed_on": "2026-10-17",
                        "bird_count": 50,
                        "chick_source": "Test hatchery",
                        "average_weight_kg": "0.04",
                    },
                },
                headers=headers,
            )
            assert flock_response.status_code == 201
            assert flock_response.json()["placed_birds"] == 50
            flock_id = flock_response.json()["id"]

            buyer_response = client.post(
                "/api/v1/buyers", json={"name": "Local buyer"}, headers=headers
            )
            assert buyer_response.status_code == 201
            buyer_id = buyer_response.json()["id"]
            today = datetime.now(ZoneInfo("Asia/Karachi")).date().isoformat()
            cross_tenant_sale = client.post(
                f"/api/v1/farms/{farm_id}/sales",
                json={
                    "flock_id": flock_id,
                    "buyer_id": str(foreign_buyer_id),
                    "sale_on": today,
                    "birds": 1,
                    "total_weight_kg": "1.000",
                    "rate_per_kg_pkr": "300.00",
                    "amount_pkr": "300.00",
                },
                headers=headers,
            )
            assert cross_tenant_sale.status_code == 404
            overdraw_response = client.post(
                f"/api/v1/farms/{farm_id}/sales",
                json={
                    "flock_id": flock_id,
                    "buyer_id": buyer_id,
                    "sale_on": today,
                    "birds": 51,
                    "total_weight_kg": "51.000",
                    "rate_per_kg_pkr": "300.00",
                    "amount_pkr": "15300.00",
                },
                headers=headers,
            )
            assert overdraw_response.status_code == 422
            sale_response = client.post(
                f"/api/v1/farms/{farm_id}/sales",
                json={
                    "flock_id": flock_id,
                    "buyer_id": buyer_id,
                    "sale_on": today,
                    "birds": 10,
                    "total_weight_kg": "10.000",
                    "rate_per_kg_pkr": "300.00",
                    "amount_pkr": "2500.00",
                    "amount_paid_pkr": "500.00",
                },
                headers=headers,
            )
            assert sale_response.status_code == 201
            outstanding = client.get("/api/v1/buyers/outstanding", headers=headers)
            assert outstanding.status_code == 200
            assert Decimal(outstanding.json()[0]["outstanding_pkr"]) == Decimal("2000.00")

            weight_response = client.post(
                f"/api/v1/flocks/{flock_id}/weight-samples",
                json={"sampled_on": today, "sample_size": 10, "average_weight_kg": "1.0"},
                headers=headers,
            )
            assert weight_response.status_code == 201
            price_response = client.post(
                f"/api/v1/farms/{farm_id}/market-prices",
                json={"effective_on": today, "price_per_kg_pkr": "300.00"},
                headers=headers,
            )
            assert price_response.status_code == 201
            cost_response = client.post(
                f"/api/v1/farms/{farm_id}/direct-costs",
                json={
                    "flock_id": flock_id,
                    "incurred_on": today,
                    "amount_pkr": "1000.00",
                    "description": "Chicks",
                },
                headers=headers,
            )
            assert cost_response.status_code == 201
            supplier_response = client.post(
                "/api/v1/suppliers", json={"name": "Feed supplier"}, headers=headers
            )
            assert supplier_response.status_code == 201
            purchase_response = client.post(
                f"/api/v1/farms/{farm_id}/feed-purchases",
                json={
                    "purchased_on": today,
                    "quantity": "10.000",
                    "unit": "kg",
                    "supplier_id": supplier_response.json()["id"],
                },
                headers=headers,
            )
            assert purchase_response.status_code == 201
            assert purchase_response.json()["supplier_id"] == supplier_response.json()["id"]
            farm_cost_response = client.post(
                f"/api/v1/farms/{farm_id}/expenses",
                json={
                    "scope": "farm",
                    "incurred_on": today,
                    "amount_pkr": "600.00",
                    "description": "Shared power",
                    "allocation_start": today,
                    "allocation_end": today,
                    "eligible_flock_ids": [flock_id],
                },
                headers=headers,
            )
            assert farm_cost_response.status_code == 201
            profit_response = client.get(
                f"/api/v1/flocks/{flock_id}/profit?as_of={today}", headers=headers
            )
            assert profit_response.status_code == 200
            profit = profit_response.json()
            assert Decimal(profit["allocated_farm_costs_pkr"]) == Decimal("600.00")
            assert Decimal(profit["actual_profit_pkr"]) == Decimal("900.00")
            assert Decimal(profit["estimated_profit_pkr"]) == Decimal("10400.00000")
            audited_actions = set(
                session.query(AuditLog.action).filter(AuditLog.tenant_id == tenant_id).all()
            )
            assert ("sale.create",) in audited_actions
            assert ("sale_payment.create",) in audited_actions
            assert ("expense.create",) in audited_actions
            dashboard_response = client.get("/api/v1/dashboard", headers=headers)
            assert dashboard_response.status_code == 200
            dashboard = dashboard_response.json()
            assert dashboard["metrics"]["live_birds"]["value"] == 40
            assert dashboard["metrics"]["live_birds"]["status"] == "partial_excludes_transfers"
            assert Decimal(dashboard["metrics"]["estimated_profit_pkr"]["value"]) == Decimal(
                "11000"
            )
            assert (
                dashboard["metrics"]["estimated_profit_pkr"]["status"]
                == "partial_excludes_shared_farm_costs"
            )

            sale_id = sale_response.json()["id"]
            rejected_sale_edit = client.patch(
                f"/api/v1/sales/{sale_id}",
                json={
                    "expected_version": 1,
                    "buyer_id": buyer_id,
                    "sale_on": today,
                    "birds": 51,
                    "total_weight_kg": "51.000",
                    "rate_per_kg_pkr": "300.00",
                    "amount_pkr": "15300.00",
                },
                headers=headers,
            )
            assert rejected_sale_edit.status_code == 422
            sale_edit = client.patch(
                f"/api/v1/sales/{sale_id}",
                json={
                    "expected_version": 1,
                    "buyer_id": buyer_id,
                    "sale_on": today,
                    "birds": 12,
                    "total_weight_kg": "12.000",
                    "rate_per_kg_pkr": "300.00",
                    "amount_pkr": "2700.00",
                },
                headers=headers,
            )
            assert sale_edit.status_code == 200
            stale_sale_edit = client.patch(
                f"/api/v1/sales/{sale_id}",
                json={
                    "expected_version": 1,
                    "buyer_id": buyer_id,
                    "sale_on": today,
                    "birds": 11,
                    "total_weight_kg": "11.000",
                    "rate_per_kg_pkr": "300.00",
                    "amount_pkr": "2600.00",
                },
                headers=headers,
            )
            assert stale_sale_edit.status_code == 409
            expense_edit = client.patch(
                f"/api/v1/expenses/{farm_cost_response.json()['id']}",
                json={
                    "expected_version": 1,
                    "scope": "farm",
                    "incurred_on": today,
                    "amount_pkr": "700.00",
                    "description": "Shared power revised",
                    "allocation_start": today,
                    "allocation_end": today,
                    "eligible_flock_ids": [flock_id],
                },
                headers=headers,
            )
            assert expense_edit.status_code == 200
            refreshed_profit = client.get(
                f"/api/v1/flocks/{flock_id}/profit?as_of={today}", headers=headers
            )
            assert refreshed_profit.status_code == 200
            assert Decimal(refreshed_profit.json()["actual_profit_pkr"]) == Decimal("1000.00")
            audited_actions = set(
                session.query(AuditLog.action).filter(AuditLog.tenant_id == tenant_id).all()
            )
            assert ("sale.update",) in audited_actions
            assert ("expense.update",) in audited_actions
            edited_audit_values = (
                session.query(AuditLog.old_value, AuditLog.new_value)
                .filter(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.action.in_(("sale.update", "expense.update")),
                )
                .all()
            )
            assert len(edited_audit_values) == 2
            assert all(old_value and new_value for old_value, new_value in edited_audit_values)

            delete_placed_flock = client.delete(f"/api/v1/flocks/{flock_id}", headers=headers)
            assert delete_placed_flock.status_code == 409
            assert delete_placed_flock.json()["error"]["message"] == (
                "Placed flocks cannot be deleted. Close the flock to retain its records."
            )
            retained_flock = client.get(f"/api/v1/flocks/{flock_id}", headers=headers)
            assert retained_flock.status_code == 200
            assert retained_flock.json()["id"] == flock_id

            over_capacity_response = client.post(
                "/api/v1/flocks",
                json={
                    "farm_id": farm_id,
                    "shed_id": shed_id,
                    "name": "Flock B",
                    "placement": {
                        "placed_on": "2026-10-17",
                        "bird_count": 51,
                        "chick_source": "Test hatchery",
                    },
                },
                headers=headers,
            )
            assert over_capacity_response.status_code == 422

            list_response = client.get("/api/v1/flocks", headers=headers)
            assert list_response.status_code == 200
            assert list_response.json()["total"] == 1
            assert list_response.json()["items"][0]["name"] == "Flock A"
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()
