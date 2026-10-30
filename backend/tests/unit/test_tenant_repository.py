from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.identity import AuditLog
from app.repositories.base import TenantContext, TenantRepository


def test_tenant_repository_requires_context() -> None:
    with pytest.raises(TypeError):
        TenantRepository(None)  # type: ignore[call-arg,arg-type]


def test_tenant_query_is_constrained_by_verified_tenant_id() -> None:
    tenant_id = uuid4()
    repository = TenantRepository(None, TenantContext(tenant_id))  # type: ignore[arg-type]
    statement = repository.scoped(AuditLog)
    assert "audit_logs.tenant_id =" in str(statement)
    assert statement.compile().params["tenant_id_1"] == tenant_id


def test_repository_rejects_models_without_tenant_scope() -> None:
    repository = TenantRepository(None, TenantContext(uuid4()))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="tenant-owned"):
        repository.scoped(str)


def test_cross_tenant_rows_are_not_returned() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tenant_a, tenant_b = uuid4(), uuid4()
    with Session(engine) as session:
        session.add_all(
            [
                AuditLog(
                    tenant_id=tenant_a, action="a", entity_type="test", created_at=datetime.now(UTC)
                ),
                AuditLog(
                    tenant_id=tenant_b, action="b", entity_type="test", created_at=datetime.now(UTC)
                ),
            ]
        )
        session.commit()
        repository = TenantRepository(session, TenantContext(tenant_a))
        rows = session.scalars(repository.scoped(AuditLog)).all()
    assert [row.action for row in rows] == ["a"]
    engine.dispose()
