from functools import lru_cache
from typing import ClassVar
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


class Settings(BaseSettings):
    DEVELOPMENT_JWT_SECRET: ClassVar[str] = "development-only-change-me-before-deployment"

    app_environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://pouktry:replace_me_local_only@localhost:5432/pouktry",
        repr=False,
    )
    log_level: str = "INFO"
    jwt_secret: str = Field(default=DEVELOPMENT_JWT_SECRET, min_length=32, repr=False)
    jwt_issuer: str = "pouktry-api"
    jwt_audience: str = "pouktry-client"
    access_token_minutes: int = Field(default=10, ge=1, le=15)
    refresh_token_days: int = Field(default=14, ge=1, le=30)
    login_max_attempts: int = 5
    login_window_seconds: int = 900
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def reject_development_secret_in_production(self) -> "Settings":
        if (
            self.app_environment.casefold() == "production"
            and self.jwt_secret == self.DEVELOPMENT_JWT_SECRET
        ):
            raise ValueError("JWT_SECRET must be explicitly configured in production")
        if self.app_environment.casefold() == "production":
            try:
                database_url = make_url(self.database_url)
            except (SQLAlchemyError, TypeError, ValueError):
                raise ValueError("DATABASE_URL must be a managed PostgreSQL URL with TLS") from None
            if (
                database_url.drivername != "postgresql+psycopg"
                or database_url.host in {None, "localhost", "127.0.0.1", "::1"}
                or database_url.password in {None, "replace_me_local_only"}
                or database_url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}
            ):
                raise ValueError("DATABASE_URL must be a managed PostgreSQL URL with TLS")
            origin = urlsplit(self.frontend_origin)
            if (
                origin.scheme != "https"
                or not origin.netloc
                or origin.path not in {"", "/"}
                or origin.query
                or origin.fragment
                or origin.username
                or origin.password
            ):
                raise ValueError("FRONTEND_ORIGIN must be an HTTPS origin in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
