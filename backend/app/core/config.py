from functools import lru_cache
from typing import ClassVar

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DEVELOPMENT_JWT_SECRET: ClassVar[str] = "development-only-change-me-before-deployment"

    app_environment: str = "development"
    database_url: str = "postgresql+psycopg://pouktry:replace_me_local_only@localhost:5432/pouktry"
    log_level: str = "INFO"
    jwt_secret: str = Field(default=DEVELOPMENT_JWT_SECRET, min_length=32)
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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
