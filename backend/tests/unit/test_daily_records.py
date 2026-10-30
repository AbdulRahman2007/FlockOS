import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import ceil
from time import perf_counter
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.authz import Principal, Role, get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models.daily_records import DailyRecord, FeedPurchase, WeightSample
from app.models.farm_operations import Farm, Flock, FlockPlacement, Shed, TenantSettings
from app.models.identity import AuditLog, AuthSession, FarmAssignment, Tenant, User


@pytest.fixture
def farm_client() -> Iterator[dict[str, object]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    tenant_id = uuid4()
    now = datetime.now(UTC)
    today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    farm = Farm(
        id=uuid4(),
        tenant_id=tenant_id,
        name="Daily Test Farm",
        location=None,
        timezone="Asia/Karachi",
        created_at=now,
        updated_at=now,
    )
    shed = Shed(
        id=uuid4(),
        tenant_id=tenant_id,
        farm_id=farm.id,
        name="Shed A",
        capacity_birds=500,
        created_at=now,
        updated_at=now,
    )
    flock = Flock(
        id=uuid4(),
        tenant_id=tenant_id,
        farm_id=farm.id,
        shed_id=shed.id,
        name="Flock A",
        status="active",
        closed_at=None,
        created_at=now,
        updated_at=now,
    )
    users: dict[Role, User] = {}
    headers: dict[Role, dict[str, str]] = {}
    for role in (Role.OWNER, Role.MANAGER, Role.WORKER, Role.ACCOUNTANT):
        user = User(
            id=uuid4(),
            tenant_id=tenant_id,
            email=f"{role.value}@example.test",
            full_name=role.value,
            password_hash="unused",
            role=role.value,
            is_active=True,
            created_at=now,
        )
        session_id = uuid4()
        session.add(
            AuthSession(
                id=session_id,
                user_id=user.id,
                refresh_token_hash=f"{role.value:0<64}"[:64],
                expires_at=now + timedelta(days=1),
                created_at=now,
            )
        )
        users[role] = user
        token = create_access_token(
            user_id=str(user.id),
            role=role.value,
            tenant_id=str(tenant_id),
            session_id=str(session_id),
        )
        headers[role] = {"Authorization": f"Bearer {token}"}
    session.add_all(
        [
            Tenant(id=tenant_id, name="Daily Test Tenant", created_at=now),
            *users.values(),
            farm,
            shed,
            flock,
            FlockPlacement(
                id=uuid4(),
                tenant_id=tenant_id,
                flock_id=flock.id,
                placed_on=today - timedelta(days=14),
                bird_count=100,
                chick_source="Test Hatchery",
                average_weight_kg=Decimal("0.040"),
                created_by=users[Role.OWNER].id,
                created_at=now,
            ),
            TenantSettings(
                tenant_id=tenant_id,
                feed_bag_size_kg=Decimal("50"),
                target_mortality_percent=None,
                target_fcr=None,
                updated_by=users[Role.OWNER].id,
                updated_at=now,
            ),
            FarmAssignment(
                id=uuid4(),
                tenant_id=tenant_id,
                user_id=users[Role.MANAGER].id,
                farm_id=farm.id,
            ),
        ]
    )
    session.commit()

    def override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "headers": headers,
                "session": session,
                "flock_id": flock.id,
                "farm_id": farm.id,
                "today": today,
                "users": users,
            }
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _daily_payload(day: date, *, deaths: int = 0) -> dict[str, object]:
    return {
        "record_date": day.isoformat(),
        "deaths": deaths,
        "culling": 0,
        "feed_used_kg": "25.000",
        "water_liters": "100.00",
        "temperature_c": "27.00",
        "notes": "",
    }


def _post_record(
    state: dict[str, object], role: Role, day: date, key: str, *, deaths: int = 0
) -> object:
    client = state["client"]
    headers = dict(state["headers"][role])
    headers["Idempotency-Key"] = key
    return client.post(
        f"/api/v1/flocks/{state['flock_id']}/daily-records",
        json=_daily_payload(day, deaths=deaths),
        headers=headers,
    )


def test_daily_submit_is_idempotent_and_conflicting_payload_is_rejected(
    farm_client: dict[str, object],
) -> None:
    day = farm_client["today"]
    key = "daily-record-submit-0001"
    first = _post_record(farm_client, Role.OWNER, day, key, deaths=3)
    retry = _post_record(farm_client, Role.OWNER, day, key, deaths=3)
    conflict = _post_record(farm_client, Role.OWNER, day, key, deaths=4)
    same_date_new_key = _post_record(farm_client, Role.OWNER, day, "daily-submit-other-02")

    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]
    assert first.json()["closing_birds"] == 97
    assert conflict.status_code == 409
    assert same_date_new_key.status_code == 409
    session = farm_client["session"]
    assert session.scalar(select(func.count()).select_from(DailyRecord)) == 1


def test_daily_submit_reports_local_sqlite_p95(farm_client: dict[str, object]) -> None:
    today = farm_client["today"]
    samples: list[float] = []
    for offset in range(14, -1, -1):
        started = perf_counter()
        response = _post_record(
            farm_client,
            Role.OWNER,
            today - timedelta(days=offset),
            f"daily-p95-benchmark-{offset:02d}-key",
        )
        samples.append((perf_counter() - started) * 1000)
        assert response.status_code == 201
    ordered = sorted(samples)
    p95 = ordered[ceil(len(ordered) * 0.95) - 1]
    print(
        f"daily submit local TestClient/SQLite p95: {p95:.2f} ms "
        f"({len(samples)} unique records, in-memory DB)"
    )
    assert len(samples) == 15


def test_daily_record_list_paginates_newest_first_and_reports_total(
    farm_client: dict[str, object],
) -> None:
    today = farm_client["today"]
    for offset in (3, 2, 1):
        response = _post_record(
            farm_client,
            Role.OWNER,
            today - timedelta(days=offset),
            f"daily-pagination-{offset:02d}-key",
        )
        assert response.status_code == 201

    client = farm_client["client"]
    url = f"/api/v1/flocks/{farm_client['flock_id']}/daily-records"
    headers = farm_client["headers"][Role.OWNER]
    newest_page = client.get(url, params={"limit": 2}, headers=headers)
    older_page = client.get(url, params={"limit": 2, "offset": 2}, headers=headers)

    assert newest_page.status_code == 200
    assert newest_page.json()["total"] == 3
    assert newest_page.json()["limit"] == 2
    assert newest_page.json()["offset"] == 0
    assert [row["record_date"] for row in newest_page.json()["items"]] == [
        (today - timedelta(days=2)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
    ]
    assert [row["record_date"] for row in older_page.json()["items"]] == [
        (today - timedelta(days=3)).isoformat()
    ]


def test_backdated_edit_recomputes_later_closing_counts_and_audits(
    farm_client: dict[str, object],
) -> None:
    today = farm_client["today"]
    first_day, second_day = today - timedelta(days=3), today - timedelta(days=2)
    first = _post_record(farm_client, Role.OWNER, first_day, "daily-first-backdate-0001", deaths=5)
    second = _post_record(
        farm_client, Role.OWNER, second_day, "daily-second-backdate-01", deaths=10
    )
    assert first.json()["closing_birds"] == 95
    assert second.json()["closing_birds"] == 85

    result = farm_client["client"].patch(
        f"/api/v1/daily-records/{first.json()['id']}",
        json={**_daily_payload(first_day, deaths=12), "expected_version": 1},
        headers=farm_client["headers"][Role.OWNER],
    )
    assert result.status_code == 200
    assert result.json()["version"] == 2
    assert result.json()["closing_birds"] == 88
    history = farm_client["client"].get(
        f"/api/v1/flocks/{farm_client['flock_id']}/daily-records",
        headers=farm_client["headers"][Role.OWNER],
    )
    assert [row["closing_birds"] for row in history.json()["items"]] == [88, 78]
    stale = farm_client["client"].patch(
        f"/api/v1/daily-records/{first.json()['id']}",
        json={**_daily_payload(first_day, deaths=13), "expected_version": 1},
        headers=farm_client["headers"][Role.OWNER],
    )
    assert stale.status_code == 409
    assert history.json()["missing_dates"]
    assert farm_client["session"].scalar(select(func.count()).select_from(AuditLog)) >= 3


def test_daily_edit_windows_apply_per_role_and_worker_is_limited_to_own_entry(
    farm_client: dict[str, object],
) -> None:
    today = farm_client["today"]
    current = _post_record(farm_client, Role.WORKER, today, "daily-worker-own-000001")
    yesterday = _post_record(
        farm_client, Role.WORKER, today - timedelta(days=1), "daily-worker-yesterday-01"
    )
    assert current.status_code == 201
    assert yesterday.status_code == 403

    within_window_date = today - timedelta(days=6)
    outside_window_date = today - timedelta(days=8)
    within = _post_record(farm_client, Role.OWNER, within_window_date, "daily-manager-window-0001")
    outside = _post_record(farm_client, Role.OWNER, outside_window_date, "daily-manager-old-000001")
    manager_edit = farm_client["client"].patch(
        f"/api/v1/daily-records/{within.json()['id']}",
        json={**_daily_payload(within_window_date, deaths=1), "expected_version": 1},
        headers=farm_client["headers"][Role.MANAGER],
    )
    manager_too_old = farm_client["client"].patch(
        f"/api/v1/daily-records/{outside.json()['id']}",
        json={**_daily_payload(outside_window_date, deaths=1), "expected_version": 1},
        headers=farm_client["headers"][Role.MANAGER],
    )
    worker_other_user = farm_client["client"].patch(
        f"/api/v1/daily-records/{within.json()['id']}",
        json={**_daily_payload(within_window_date, deaths=2), "expected_version": 1},
        headers=farm_client["headers"][Role.WORKER],
    )
    assert manager_edit.status_code == 200

    assert manager_too_old.status_code == 403
    assert worker_other_user.status_code == 403


def test_owner_configures_manager_and_worker_edit_windows(
    farm_client: dict[str, object],
) -> None:
    client = farm_client["client"]
    owner = farm_client["headers"][Role.OWNER]
    configured = client.put(
        "/api/v1/settings",
        json={"manager_daily_window_days": 10, "worker_daily_window_days": 2},
        headers=owner,
    )
    assert configured.status_code == 200
    assert configured.json()["manager_daily_window_days"] == 10
    assert configured.json()["worker_daily_window_days"] == 2

    day = farm_client["today"] - timedelta(days=8)
    manager_record = _post_record(farm_client, Role.OWNER, day, "daily-config-manager-entry-01")
    manager_edit = client.patch(
        f"/api/v1/daily-records/{manager_record.json()['id']}",
        json={**_daily_payload(day, deaths=1), "expected_version": 1},
        headers=farm_client["headers"][Role.MANAGER],
    )
    assert manager_edit.status_code == 200

    worker_day = farm_client["today"] - timedelta(days=1)
    worker_record = _post_record(
        farm_client, Role.WORKER, worker_day, "daily-config-worker-entry-01"
    )
    worker_edit = client.patch(
        f"/api/v1/daily-records/{worker_record.json()['id']}",
        json={**_daily_payload(worker_day, deaths=1), "expected_version": 1},
        headers=farm_client["headers"][Role.WORKER],
    )
    assert worker_record.status_code == 201
    assert worker_edit.status_code == 200


def test_weekly_weight_samples_and_feed_purchase_bag_conversion(
    farm_client: dict[str, object],
) -> None:
    today = farm_client["today"]
    client = farm_client["client"]
    headers = farm_client["headers"][Role.OWNER]
    flock_id: UUID = farm_client["flock_id"]
    sample = client.post(
        f"/api/v1/flocks/{flock_id}/weight-samples",
        json={
            "sampled_on": (today - timedelta(days=7)).isoformat(),
            "sample_size": 50,
            "average_weight_kg": "0.550",
        },
        headers=headers,
    )
    too_soon = client.post(
        f"/api/v1/flocks/{flock_id}/weight-samples",
        json={
            "sampled_on": (today - timedelta(days=1)).isoformat(),
            "sample_size": 50,
            "average_weight_kg": "0.700",
        },
        headers=headers,
    )
    purchase = client.post(
        f"/api/v1/farms/{farm_client['farm_id']}/feed-purchases",
        json={
            "purchased_on": today.isoformat(),
            "quantity": "3",
            "unit": "bags",
            "amount_pkr": "7200.00",
            "supplier_name": "Feed supplier",
        },
        headers=headers,
    )
    assert sample.status_code == 201
    assert too_soon.status_code == 409
    assert purchase.status_code == 201
    assert purchase.json()["quantity_kg"] == "150.000"
    assert farm_client["session"].scalar(select(func.count()).select_from(WeightSample)) == 1
    assert farm_client["session"].scalar(select(func.count()).select_from(FeedPurchase)) == 1
    weight_page = client.get(
        f"/api/v1/flocks/{flock_id}/weight-samples",
        params={"limit": 1},
        headers=headers,
    )
    purchase_page = client.get(
        f"/api/v1/farms/{farm_client['farm_id']}/feed-purchases",
        params={"limit": 1},
        headers=headers,
    )
    assert weight_page.status_code == 200
    assert weight_page.json()["total"] == 1
    assert len(weight_page.json()["items"]) == 1
    assert purchase_page.status_code == 200
    assert purchase_page.json()["total"] == 1
    assert len(purchase_page.json()["items"]) == 1


def test_reports_match_dashboard_and_scope_by_role(farm_client: dict[str, object]) -> None:
    from app.models.farm_operations import Expense

    today = farm_client["today"]
    response = _post_record(farm_client, Role.OWNER, today, "report-reconcile-daily-0001", deaths=3)
    assert response.status_code == 201

    owner = farm_client["users"][Role.OWNER]
    session = farm_client["session"]
    session.add(
        Expense(
            id=uuid4(),
            tenant_id=owner.tenant_id,
            farm_id=farm_client["farm_id"],
            flock_id=None,
            supplier_id=None,
            scope="farm",
            incurred_on=today,
            amount_pkr=Decimal("1250.00"),
            description="Farm electricity",
            allocation_start=today - timedelta(days=7),
            allocation_end=today,
            version=1,
            created_by=owner.id,
            created_at=datetime.now(UTC),
            updated_by=owner.id,
        )
    )
    session.commit()

    client = farm_client["client"]
    owner_headers = farm_client["headers"][Role.OWNER]
    params = {
        "start_date": (today - timedelta(days=14)).isoformat(),
        "end_date": today.isoformat(),
        "farm_id": str(farm_client["farm_id"]),
        "flock_id": str(farm_client["flock_id"]),
    }
    flock_report = client.get("/api/v1/reports/flocks", params=params, headers=owner_headers)
    dashboard = client.get("/api/v1/dashboard", headers=owner_headers)
    mortality = client.get("/api/v1/reports/mortality", params=params, headers=owner_headers)
    feed = client.get("/api/v1/reports/feed", params=params, headers=owner_headers)
    csv_export = client.get("/api/v1/reports/feed/export.csv", params=params, headers=owner_headers)
    financial = client.get(
        "/api/v1/reports/financial",
        params={key: value for key, value in params.items() if key != "flock_id"},
        headers=owner_headers,
    )

    assert flock_report.status_code == 200
    assert dashboard.status_code == 200
    assert (
        flock_report.json()["totals"]["live_birds"]
        == dashboard.json()["metrics"]["live_birds"]["value"]
        == 97
    )
    assert mortality.json()["totals"]["deaths"] == 3
    assert mortality.json()["items"][0]["mortality_percent"] == "3.00"
    assert feed.json()["totals"]["feed_used_kg"] == "25.000"
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert "feed_used_kg" in csv_export.text
    assert financial.status_code == 200
    assert financial.json()["totals"]["expense"] == "1250.00"

    worker_report = client.get(
        "/api/v1/reports/flocks",
        params=params,
        headers=farm_client["headers"][Role.WORKER],
    )
    assert worker_report.status_code == 403


def test_ten_thousand_row_csv_export_streams_within_approved_budget(
    farm_client: dict[str, object],
) -> None:
    import tracemalloc

    from app.api.v1.reports import export_report_csv

    session = farm_client["session"]
    owner = farm_client["users"][Role.OWNER]
    today = farm_client["today"]
    earliest = today - timedelta(days=9_999)
    session.add(
        FlockPlacement(
            id=uuid4(),
            tenant_id=owner.tenant_id,
            flock_id=farm_client["flock_id"],
            placed_on=earliest,
            bird_count=1,
            chick_source="Export fixture",
            average_weight_kg=None,
            created_by=owner.id,
            created_at=datetime.now(UTC),
        )
    )
    records = [
        DailyRecord(
            id=uuid4(),
            tenant_id=owner.tenant_id,
            flock_id=farm_client["flock_id"],
            record_date=earliest + timedelta(days=index),
            deaths=0,
            culling=0,
            feed_used_kg=Decimal("0.001"),
            water_liters=Decimal("0.01"),
            temperature_c=Decimal("27.00"),
            notes=None,
            version=1,
            idempotency_key=f"export-10k-{index:05d}",
            request_hash="a" * 64,
            created_by=owner.id,
            updated_by=owner.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        for index in range(10_000)
    ]
    session.add_all(records)
    session.commit()

    response = export_report_csv(
        "feed",
        session,
        Principal(user_id=owner.id, tenant_id=owner.tenant_id, role=Role.OWNER),
        start_date=earliest,
        end_date=today,
        farm_id=farm_client["farm_id"],
        flock_id=farm_client["flock_id"],
    )
    line_count = 0

    async def consume_stream() -> None:
        nonlocal line_count
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                line_count += chunk.count(b"\n")
            else:
                line_count += str(chunk).count("\n")

    tracemalloc.start()
    started = perf_counter()
    asyncio.run(consume_stream())
    elapsed_seconds = perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(
        f"10,000-row CSV export: {elapsed_seconds:.3f}s; "
        f"peak traced allocation {peak_bytes / (1024 * 1024):.2f} MiB"
    )
    assert line_count == 10_001
    assert elapsed_seconds < 10
    assert peak_bytes < 64 * 1024 * 1024
