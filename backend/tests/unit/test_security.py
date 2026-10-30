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
        _env_file=None,
    )
    assert settings.app_environment == "production"


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
