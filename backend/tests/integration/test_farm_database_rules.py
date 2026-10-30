import os
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.farm_operations import Farm, Flock, FlockPlacement, Shed
from app.models.identity import Tenant, User

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")


def test_postgres_rejects_placements_over_shed_capacity() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(Tenant(id=tenant_id, name="Capacity test", created_at=now))
        session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"{user_id}@example.test",
                full_name="Test Owner",
                password_hash="unused",
                role="owner",
                is_active=True,
                created_at=now,
            )
        )
        session.flush()
        farm_id, shed_id, flock_id = uuid4(), uuid4(), uuid4()
        session.add(
            Farm(
                id=farm_id,
                tenant_id=tenant_id,
                name="Capacity farm",
                timezone="Asia/Karachi",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Shed(
                id=shed_id,
                tenant_id=tenant_id,
                farm_id=farm_id,
                name="Shed 1",
                capacity_birds=100,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            Flock(
                id=flock_id,
                tenant_id=tenant_id,
                farm_id=farm_id,
                shed_id=shed_id,
                name="Flock 1",
                status="active",
                closed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            FlockPlacement(
                id=uuid4(),
                tenant_id=tenant_id,
                flock_id=flock_id,
                placed_on=date.today(),
                bird_count=101,
                chick_source="Test hatchery",
                average_weight_kg=None,
                created_by=user_id,
                created_at=now,
            )
        )
        with pytest.raises(DBAPIError, match="capacity"):
            session.flush()
        session.rollback()
    engine.dispose()


def test_postgres_rejects_placement_on_a_closed_flock() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    tenant_id, user_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(Tenant(id=tenant_id, name="Closed flock test", created_at=now))
        session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"{user_id}@example.test",
                full_name="Test Owner",
                password_hash="unused",
                role="owner",
                is_active=True,
                created_at=now,
            )
        )
        session.flush()
        farm_id, shed_id, flock_id = uuid4(), uuid4(), uuid4()
        session.add(
            Farm(
                id=farm_id,
                tenant_id=tenant_id,
                name="Closed flock farm",
                timezone="Asia/Karachi",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Shed(
                id=shed_id,
                tenant_id=tenant_id,
                farm_id=farm_id,
                name="Shed 1",
                capacity_birds=100,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            Flock(
                id=flock_id,
                tenant_id=tenant_id,
                farm_id=farm_id,
                shed_id=shed_id,
                name="Closed flock",
                status="closed",
                closed_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            FlockPlacement(
                id=uuid4(),
                tenant_id=tenant_id,
                flock_id=flock_id,
                placed_on=date.today(),
                bird_count=10,
                chick_source="Test hatchery",
                average_weight_kg=None,
                created_by=user_id,
                created_at=now,
            )
        )
        with pytest.raises(DBAPIError, match="closed flock is locked"):
            session.flush()
        session.rollback()
    engine.dispose()
