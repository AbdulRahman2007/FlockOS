import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-user-password-for-timing-only")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return password_hash.verify(password, encoded_hash)
    except (UnknownHashError, ValueError, TypeError):
        return False


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_access_token(*, user_id: str, role: str, tenant_id: str | None, session_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": secrets.token_urlsafe(16),
        "sid": session_id,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "role", "iat", "exp", "iss", "aud", "jti", "sid"]},
    )
    return cast(dict[str, object], claims)
