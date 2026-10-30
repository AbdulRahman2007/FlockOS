"""Create the first platform administrator through an explicit operator action."""

import argparse
from datetime import UTC, datetime
from getpass import getpass

from sqlalchemy import select

from app.core.authz import Role
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.identity import AuditLog, User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    arguments = parser.parse_args()
    password = getpass("Password (minimum 12 characters): ")
    if len(password) < 12:
        parser.error("Password must be at least 12 characters")

    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        existing = session.scalar(select(User.id).where(User.role == Role.SUPER_ADMIN.value))
        if existing is not None:
            parser.error("A Super Admin already exists; bootstrap is single-use")
        user = User(
            email=arguments.email.lower(),
            full_name=arguments.name,
            password_hash=hash_password(password),
            role=Role.SUPER_ADMIN.value,
            tenant_id=None,
            is_active=True,
            created_at=now,
        )
        session.add(user)
        session.flush()
        session.add(
            AuditLog(
                tenant_id=None,
                actor_user_id=user.id,
                action="identity.bootstrap",
                entity_type="user",
                entity_id=str(user.id),
                created_at=now,
            )
        )


if __name__ == "__main__":
    main()
