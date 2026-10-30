import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_opaque_token,
    token_digest,
    verify_password,
)


def test_production_settings_reject_the_development_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET must be explicitly configured"):
        Settings(
            app_environment="production",
            jwt_secret=Settings.DEVELOPMENT_JWT_SECRET,
            _env_file=None,
        )


def test_production_settings_accept_an_explicit_jwt_secret() -> None:
    settings = Settings(
        app_environment="production",
        jwt_secret="production-secret-value-that-is-long-enough-1234",
        database_url=(
            "postgresql+psycopg://pouktry:secret@db.example.com/pouktry?sslmode=verify-full"
        ),
        frontend_origin="https://farm.example.com",
        _env_file=None,
    )
    assert settings.app_environment == "production"


@pytest.mark.parametrize(
    ("database_url", "frontend_origin"),
    [
        (
            "postgresql+psycopg://pouktry:secret@localhost/pouktry?sslmode=require",
            "https://farm.example.com",
        ),
        (
            "postgresql+psycopg://pouktry:secret@db.example.com/pouktry",
            "https://farm.example.com",
        ),
        (
            "postgresql+psycopg://pouktry:secret@db.example.com/pouktry?sslmode=require",
            "http://farm.example.com",
        ),
    ],
)
def test_production_settings_reject_local_or_insecure_endpoints(
    database_url: str, frontend_origin: str
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_environment="production",
            jwt_secret="production-secret-value-that-is-long-enough-1234",
            database_url=database_url,
            frontend_origin=frontend_origin,
            _env_file=None,
        )


def test_settings_representation_does_not_expose_secrets() -> None:
    database_password = "db-password-that-must-not-appear"
    jwt_secret = "jwt-secret-that-must-not-appear-123456789"
    settings = Settings(
        database_url=f"postgresql+psycopg://pouktry:{database_password}@localhost/pouktry",
        jwt_secret=jwt_secret,
        _env_file=None,
    )
    assert database_password not in repr(settings)
    assert jwt_secret not in repr(settings)


def test_password_hash_is_verifiable_and_not_plaintext() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2")
    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_has_verified_identity_claims() -> None:
    token = create_access_token(
        user_id="user-1", role="owner", tenant_id="tenant-1", session_id="session-1"
    )
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["role"] == "owner"
    assert claims["tenant_id"] == "tenant-1"
    assert claims["sid"] == "session-1"


def test_refresh_tokens_are_random_and_only_digest_is_persisted() -> None:
    first = new_opaque_token()
    second = new_opaque_token()
    assert first != second
    assert token_digest(first) != first
    assert len(token_digest(first)) == 64
