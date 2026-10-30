import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.authz import Principal, Role
from app.domain.calculations import DailyBirdFacts, calculate_bird_ledger, recompute_bird_ledger
from app.models.daily_records import DailyRecord, FeedPurchase, WeightSample
from app.models.farm_operations import Flock, FlockPlacement, Sale
from app.repositories.base import TenantContext
from app.repositories.daily_records import DailyRepository
from app.schemas.daily_records import DailyRecordCreate, DailyRecordUpdate, FeedPurchaseCreate
from app.services.audit import record_audit


class DailyRecordError(ValueError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def local_today(flock: Flock, repository: DailyRepository) -> date:
    farm = repository.farm_for_flock(flock)
    if farm is None:
        raise DailyRecordError(404, "Flock not found")
    return datetime.now(ZoneInfo(farm.timezone)).date()


def enforce_record_date(
    flock: Flock, data_date: date, principal: Principal, repo: DailyRepository
) -> None:
    today = local_today(flock, repo)
    if data_date > today:
        raise DailyRecordError(422, "Daily records cannot be entered for a future date")
    settings = repo.settings()
    manager_window_days = settings.manager_daily_window_days if settings else 7
    worker_window_days = settings.worker_daily_window_days if settings else 1
    if principal.role is Role.WORKER and data_date < today - timedelta(days=worker_window_days - 1):
        raise DailyRecordError(403, "This record is outside the configured Worker edit window")
    if principal.role is Role.MANAGER and data_date < today - timedelta(
        days=manager_window_days - 1
    ):
        raise DailyRecordError(403, "This record is outside the configured Manager edit window")


def _request_hash(flock_id: UUID, payload: DailyRecordCreate) -> str:
    values = payload.model_dump(mode="json")
    raw = json.dumps({"flock_id": str(flock_id), **values}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ledger_facts(
    placements: list[FlockPlacement],
    records: list[DailyRecord],
    sales: list[Sale] | None = None,
    replace_record: DailyRecord | None = None,
    replacement: DailyRecordCreate | None = None,
) -> tuple[int, list[DailyBirdFacts]]:
    if not placements:
        raise DailyRecordError(409, "Flock has no placement")
    placement_rows = sorted(placements, key=lambda row: (row.placed_on, str(row.id)))
    initial = placement_rows[0]
    placed_birds = initial.bird_count
    movements: dict[date, dict[str, int]] = {}
    for placement in placement_rows[1:]:
        current = movements.setdefault(placement.placed_on, {})
        current["transferred_in"] = current.get("transferred_in", 0) + placement.bird_count
    for record in records:
        source = (
            replacement if replace_record is not None and record.id == replace_record.id else None
        )
        record_date = source.record_date if source is not None else record.record_date
        deaths = source.deaths if source is not None else record.deaths
        culling = source.culling if source is not None else record.culling
        current = movements.setdefault(record_date, {})
        current["deaths"] = current.get("deaths", 0) + deaths
        current["culling"] = current.get("culling", 0) + culling
    for sale in sales or []:
        current = movements.setdefault(sale.sale_on, {})
        current["sold"] = current.get("sold", 0) + sale.birds
    if replacement is not None and replace_record is None:
        current = movements.setdefault(replacement.record_date, {})
        current["deaths"] = current.get("deaths", 0) + replacement.deaths
        current["culling"] = current.get("culling", 0) + replacement.culling
    facts = [DailyBirdFacts(day=day, **values) for day, values in sorted(movements.items())]
    return placed_birds, facts


def closing_bird_counts(repo: DailyRepository, flock_id: UUID) -> dict[date, int]:
    placements = repo.placements(flock_id)
    records = repo.records(flock_id)
    placed_birds, facts = _ledger_facts(placements, records, repo.sales(flock_id))
    balances = calculate_bird_ledger(placed_birds, facts)
    return {balance.day: balance.closing_birds for balance in balances}


def create_daily_record(
    session: Session,
    principal: Principal,
    flock: Flock,
    payload: DailyRecordCreate,
    idempotency_key: str,
) -> tuple[DailyRecord, bool]:
    if principal.tenant_id is None:
        raise DailyRecordError(403, "Not permitted")
    repo = DailyRepository(session, TenantContext(principal.tenant_id))
    flock = repo.flock(flock.id, lock=True) or flock
    request_hash = _request_hash(flock.id, payload)
    replay = repo.idempotent_record(principal.user_id, idempotency_key, lock=True)
    if replay is not None:
        if replay.request_hash != request_hash:
            raise DailyRecordError(409, "Idempotency key was already used for different data")
        return replay, False
    if flock.status != "active":
        raise DailyRecordError(423, "Closed flocks are locked")
    enforce_record_date(flock, payload.record_date, principal, repo)
    placements = repo.placements(flock.id)
    if not placements or payload.record_date < min(row.placed_on for row in placements):
        raise DailyRecordError(422, "Record date cannot be before flock placement")
    if repo.record_for_date(flock.id, payload.record_date) is not None:
        raise DailyRecordError(409, "A daily record already exists for this flock and date")
    existing_records = repo.records(flock.id)
    placed_birds, facts = _ledger_facts(
        placements, existing_records, repo.sales(flock.id), replacement=payload
    )
    try:
        calculate_bird_ledger(placed_birds, facts)
    except ValueError as error:
        raise DailyRecordError(422, str(error)) from None
    now = datetime.now(UTC)
    row = DailyRecord(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        flock_id=flock.id,
        record_date=payload.record_date,
        deaths=payload.deaths,
        culling=payload.culling,
        feed_used_kg=payload.feed_used_kg,
        water_liters=payload.water_liters,
        temperature_c=payload.temperature_c,
        notes=payload.notes,
        version=1,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=principal.user_id,
        updated_by=principal.user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="daily_record.create",
        entity_type="daily_record",
        entity_id=str(row.id),
        new_value=json.dumps(payload.model_dump(mode="json"), sort_keys=True),
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        replay = repo.idempotent_record(principal.user_id, idempotency_key)
        if replay is not None and replay.request_hash == request_hash:
            return replay, False
        if replay is not None:
            raise DailyRecordError(
                409, "Idempotency key was already used for different data"
            ) from None
        raise DailyRecordError(
            409, "A daily record already exists for this flock and date"
        ) from None
    return row, True


def update_daily_record(
    session: Session, principal: Principal, record: DailyRecord, payload: DailyRecordUpdate
) -> DailyRecord:
    if principal.tenant_id is None:
        raise DailyRecordError(403, "Not permitted")
    repo = DailyRepository(session, TenantContext(principal.tenant_id))
    flock = repo.flock(record.flock_id, lock=True)
    if flock is None:
        raise DailyRecordError(404, "Daily record not found")
    record = repo.record(record.id, lock=True) or record
    if flock.status != "active":
        raise DailyRecordError(423, "Closed flocks are locked")
    if principal.role is Role.WORKER and record.created_by != principal.user_id:
        raise DailyRecordError(403, "Workers can edit only their own daily records")
    if record.version != payload.expected_version:
        raise DailyRecordError(409, "This record changed. Reload it before saving your edit.")
    enforce_record_date(flock, record.record_date, principal, repo)
    if payload.record_date != record.record_date:
        enforce_record_date(flock, payload.record_date, principal, repo)
        conflict = repo.record_for_date(flock.id, payload.record_date)
        if conflict is not None and conflict.id != record.id:
            raise DailyRecordError(409, "A daily record already exists for this flock and date")
    placements = repo.placements(flock.id)
    if not placements or payload.record_date < min(row.placed_on for row in placements):
        raise DailyRecordError(422, "Record date cannot be before flock placement")
    records = repo.records(flock.id)
    placed_birds, facts = _ledger_facts(placements, records, repo.sales(flock.id), record, payload)
    try:
        recompute_bird_ledger(
            placed_birds, facts, changed_from=min(record.record_date, payload.record_date)
        )
    except ValueError as error:
        raise DailyRecordError(422, str(error)) from None
    old_value = json.dumps(
        {
            "record_date": record.record_date.isoformat(),
            "deaths": record.deaths,
            "culling": record.culling,
            "feed_used_kg": str(record.feed_used_kg),
            "water_liters": str(record.water_liters),
            "temperature_c": str(record.temperature_c),
            "notes": record.notes,
            "version": record.version,
        },
        sort_keys=True,
    )
    record.record_date = payload.record_date
    record.deaths = payload.deaths
    record.culling = payload.culling
    record.feed_used_kg = payload.feed_used_kg
    record.water_liters = payload.water_liters
    record.temperature_c = payload.temperature_c
    record.notes = payload.notes
    record.updated_by = principal.user_id
    record.updated_at = datetime.now(UTC)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="daily_record.update",
        entity_type="daily_record",
        entity_id=str(record.id),
        old_value=old_value,
        new_value=json.dumps(payload.model_dump(mode="json"), sort_keys=True),
    )
    try:
        session.commit()
    except (IntegrityError, StaleDataError):
        session.rollback()
        raise DailyRecordError(
            409, "This record changed or conflicts with another submission"
        ) from None
    return record


def create_weight_sample(
    session: Session,
    principal: Principal,
    flock: Flock,
    sampled_on: date,
    sample_size: int,
    average_weight_kg: Decimal,
) -> WeightSample:
    if principal.tenant_id is None:
        raise DailyRecordError(403, "Not permitted")
    repo = DailyRepository(session, TenantContext(principal.tenant_id))
    flock = repo.flock(flock.id, lock=True) or flock
    if flock.status != "active":
        raise DailyRecordError(423, "Closed flocks are locked")
    enforce_record_date(flock, sampled_on, principal, repo)
    placements = repo.placements(flock.id)
    if not placements or sampled_on < min(row.placed_on for row in placements):
        raise DailyRecordError(422, "Sample date cannot be before flock placement")
    samples = repo.weight_samples(flock.id)
    if any(abs((sample.sampled_on - sampled_on).days) < 7 for sample in samples):
        raise DailyRecordError(409, "Weight samples must be at least 7 days apart")
    row = WeightSample(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        flock_id=flock.id,
        sampled_on=sampled_on,
        sample_size=sample_size,
        average_weight_kg=average_weight_kg,
        created_by=principal.user_id,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="weight_sample.create",
        entity_type="weight_sample",
        entity_id=str(row.id),
        new_value=json.dumps(
            {
                "sampled_on": sampled_on.isoformat(),
                "sample_size": sample_size,
                "average_weight_kg": str(average_weight_kg),
            },
            sort_keys=True,
        ),
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DailyRecordError(409, "A weight sample already exists for that date") from None
    return row


def create_feed_purchase(
    session: Session,
    principal: Principal,
    farm_id: UUID,
    payload: FeedPurchaseCreate,
    bag_size_kg: Decimal | None,
) -> FeedPurchase:
    if principal.tenant_id is None:
        raise DailyRecordError(403, "Not permitted")
    if payload.unit == "bags" and bag_size_kg is None:
        raise DailyRecordError(422, "Set the tenant feed bag size before recording bag purchases")
    quantity_kg = (
        payload.quantity * bag_size_kg
        if payload.unit == "bags" and bag_size_kg
        else payload.quantity
    )
    row = FeedPurchase(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        farm_id=farm_id,
        purchased_on=payload.purchased_on,
        quantity=payload.quantity,
        unit=payload.unit,
        bag_size_kg=bag_size_kg if payload.unit == "bags" else None,
        quantity_kg=quantity_kg,
        amount_pkr=payload.amount_pkr,
        supplier_name=payload.supplier_name,
        supplier_id=payload.supplier_id,
        notes=payload.notes,
        created_by=principal.user_id,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="feed_purchase.create",
        entity_type="feed_purchase",
        entity_id=str(row.id),
        new_value=json.dumps(payload.model_dump(mode="json"), sort_keys=True),
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DailyRecordError(409, "The feed purchase conflicts with existing farm data") from None
    return row
