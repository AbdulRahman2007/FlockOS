"""Seed a disposable PostgreSQL database and measure authenticated read endpoints."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.engine import Engine, make_url

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings  # noqa: E402

settings = get_settings()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", type=int, default=5435)
parser.add_argument("--requests-per-endpoint", type=int, default=50)
parser.add_argument("--workers", type=int, default=16)
arguments = parser.parse_args()
settings.database_url = make_url(settings.database_url).set(port=arguments.port).render_as_string(
    hide_password=False
)
os.environ["DATABASE_URL"] = settings.database_url

from alembic import command as alembic_command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.authz import Role  # noqa: E402
from app.core.security import create_access_token, hash_password, new_opaque_token, token_digest  # noqa: E402
from app.main import app  # noqa: E402
from app.models.daily_records import DailyRecord, WeightSample  # noqa: E402
from app.models.farm_operations import Farm, Flock, FlockPlacement, Shed  # noqa: E402
from app.models.identity import AuthSession, Tenant, User  # noqa: E402


def percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, int(len(ordered) * 0.95 + 0.999999) - 1)]


def seed_database(engine: Engine) -> tuple[UUID, UUID, UUID, date, str]:
    tenant_count = 100
    users_per_tenant = 10
    history_days = 365 * 3
    now = datetime.now(UTC)
    today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    history_start = today - timedelta(days=history_days - 1)
    tenants = [uuid4() for _ in range(tenant_count)]
    users = [[uuid4() for _ in range(users_per_tenant)] for _ in tenants]
    farms = [uuid4() for _ in tenants]
    sheds = [uuid4() for _ in tenants]
    flocks = [uuid4() for _ in tenants]
    shared_hash = hash_password("phase10-load-only-password")

    with engine.begin() as connection:
        existing = connection.scalar(
            select(Tenant.id).where(Tenant.name == "P10 Load Tenant 000")
        )
        if existing is not None:
            raise RuntimeError("Load fixture already exists; use a fresh disposable database")

        connection.execute(
            insert(Tenant),
            [
                {
                    "id": tenant_id,
                    "name": f"P10 Load Tenant {index:03}",
                    "plan": None,
                    "user_limit": None,
                    "created_at": now,
                }
                for index, tenant_id in enumerate(tenants)
            ],
        )
        connection.execute(
            insert(User),
            [
                {
                    "id": user_id,
                    "tenant_id": tenant_id,
                    "email": f"p10-{tenant_index:03}-{user_index:02}@example.invalid",
                    "full_name": f"Load User {tenant_index:03}-{user_index:02}",
                    "password_hash": shared_hash,
                    "role": Role.OWNER.value if user_index == 0 else Role.WORKER.value,
                    "is_active": True,
                    "created_at": now,
                }
                for tenant_index, (tenant_id, tenant_users) in enumerate(
                    zip(tenants, users, strict=True)
                )
                for user_index, user_id in enumerate(tenant_users)
            ],
        )
        connection.execute(
            insert(Farm),
            [
                {
                    "id": farms[index],
                    "tenant_id": tenant_id,
                    "name": f"Load Farm {index:03}",
                    "location": None,
                    "timezone": "Asia/Karachi",
                    "created_at": now,
                    "updated_at": now,
                }
                for index, tenant_id in enumerate(tenants)
            ],
        )
        connection.execute(
            insert(Shed),
            [
                {
                    "id": sheds[index],
                    "tenant_id": tenant_id,
                    "farm_id": farms[index],
                    "name": "Load Shed 1",
                    "capacity_birds": 5000,
                    "created_at": now,
                    "updated_at": now,
                }
                for index, tenant_id in enumerate(tenants)
            ],
        )
        connection.execute(
            insert(Flock),
            [
                {
                    "id": flocks[index],
                    "tenant_id": tenant_id,
                    "farm_id": farms[index],
                    "shed_id": sheds[index],
                    "name": "Load Flock 1",
                    "status": "active",
                    "closed_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
                for index, tenant_id in enumerate(tenants)
            ],
        )
        connection.execute(
            insert(FlockPlacement),
            [
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "flock_id": flocks[index],
                    "placed_on": history_start,
                    "bird_count": 5000,
                    "chick_source": "Synthetic Phase 10 load fixture",
                    "average_weight_kg": None,
                    "created_by": users[index][0],
                    "created_at": now,
                }
                for index, tenant_id in enumerate(tenants)
            ],
        )
        for tenant_index, tenant_id in enumerate(tenants):
            daily_rows = []
            weight_rows = []
            for day_index in range(history_days):
                sample_date = history_start + timedelta(days=day_index)
                daily_rows.append(
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "flock_id": flocks[tenant_index],
                        "record_date": sample_date,
                        "deaths": 1 if day_index % 10 == 0 else 0,
                        "culling": 0,
                        "feed_used_kg": 140,
                        "water_liters": 500,
                        "temperature_c": 27,
                        "notes": None,
                        "version": 1,
                        "idempotency_key": f"p10-{tenant_index:03}-{day_index:04}",
                        "request_hash": "a" * 64,
                        "created_by": users[tenant_index][0],
                        "updated_by": users[tenant_index][0],
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                if day_index % 7 == 0:
                    weight_rows.append(
                        {
                            "id": uuid4(),
                            "tenant_id": tenant_id,
                            "flock_id": flocks[tenant_index],
                            "sampled_on": sample_date,
                            "sample_size": 20,
                            "average_weight_kg": 1.5,
                            "created_by": users[tenant_index][0],
                            "created_at": now,
                        }
                    )
            connection.execute(insert(DailyRecord), daily_rows)
            connection.execute(insert(WeightSample), weight_rows)

        raw_refresh_token = new_opaque_token()
        session_id = uuid4()
        connection.execute(
            insert(AuthSession),
            {
                "id": session_id,
                "user_id": users[0][0],
                "refresh_token_hash": token_digest(raw_refresh_token),
                "expires_at": now + timedelta(days=1),
                "revoked_at": None,
                "created_at": now,
            },
        )

    token = create_access_token(
        user_id=str(users[0][0]),
        role=Role.OWNER.value,
        tenant_id=str(tenants[0]),
        session_id=str(session_id),
    )
    return tenants[0], flocks[0], farms[0], history_start, token


def main() -> None:
    alembic_config = AlembicConfig("backend/alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    alembic_command.upgrade(alembic_config, "head")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        tenant_id, flock_id, farm_id, history_start, token = seed_database(engine)
        today = datetime.now(ZoneInfo("Asia/Karachi")).date()
        headers = {"Authorization": f"Bearer {token}"}
        paths = {
            "farms": "/api/v1/farms?limit=100",
            "flocks": "/api/v1/flocks?limit=100",
            "dashboard": "/api/v1/dashboard",
            "feed_report": (
                f"/api/v1/reports/feed?start_date={history_start.isoformat()}"
                f"&end_date={today.isoformat()}&farm_id={farm_id}&flock_id={flock_id}&limit=100"
            ),
        }
        latencies: dict[str, list[float]] = {name: [] for name in paths}
        with TestClient(app) as client:
            def request_once(name: str) -> tuple[str, float]:
                started = perf_counter()
                response = client.get(paths[name], headers=headers)
                elapsed = (perf_counter() - started) * 1000
                if response.status_code != 200:
                    raise RuntimeError(f"{name} returned HTTP {response.status_code}")
                return name, elapsed

            work = [name for name in paths for _ in range(arguments.requests_per_endpoint)]
            with ThreadPoolExecutor(max_workers=arguments.workers) as executor:
                for name, elapsed in executor.map(request_once, work):
                    latencies[name].append(elapsed)

        plans = []
        with engine.connect() as connection:
            plan = connection.execute(
                text(
                    "EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM daily_records "
                    "WHERE tenant_id = :tenant_id AND flock_id = :flock_id "
                    "AND record_date BETWEEN :start_date AND :end_date "
                    "ORDER BY record_date DESC LIMIT 100"
                ),
                {
                    "tenant_id": tenant_id,
                    "flock_id": flock_id,
                    "start_date": history_start,
                    "end_date": today,
                },
            ).scalars()
            plans = list(plan)

        summary = {
            "seed": {
                "tenants": 100,
                "users": 1000,
                "farms": 100,
                "flocks": 100,
                "daily_records": 100 * 365 * 3,
                "history_days_per_flock": 365 * 3,
            },
            "requests_per_endpoint": arguments.requests_per_endpoint,
            "workers": arguments.workers,
            "p95_ms": {
                name: round(percentile_95(values), 2) for name, values in latencies.items()
            },
            "budgets_met": {
                name: percentile_95(values) < (500 if name == "dashboard" else 300)
                for name, values in latencies.items()
            },
            "daily_record_query_plan": plans,
        }
        print(json.dumps(summary, indent=2))
        if not all(summary["budgets_met"].values()):
            raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
