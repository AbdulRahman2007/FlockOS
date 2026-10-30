from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.identity import AuditLog


def record_audit(
    session: Session,
    *,
    tenant_id: UUID | None,
    actor_user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        created_at=datetime.now(UTC),
    )
    session.add(entry)
    return entry
