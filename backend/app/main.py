from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine

configure_logging(get_settings().log_level)
logger = get_logger(__name__)


def database_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("readiness_check_failed", dependency="postgresql")
        return False
    return True


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("application_starting", environment=settings.app_environment)
    yield
    engine.dispose()
    logger.info("application_stopped")


app = FastAPI(
    title="POUKTRY API",
    version="0.1.0",
    description="API foundation for the POUKTRY poultry farm management platform.",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
def readiness() -> dict[str, str]:
    if not database_ready():
        raise HTTPException(status_code=503, detail="Service is not ready")
    return {"status": "ready"}
