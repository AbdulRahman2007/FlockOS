from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ExceptionHandler

from app.api.v1.auth import router as auth_router
from app.api.v1.daily_records import router as daily_records_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.farm_resources import router as farm_resources_router
from app.api.v1.farms import router as farms_router
from app.api.v1.finance import router as finance_router
from app.api.v1.feed_stock import router as feed_stock_router
from app.api.v1.reports import router as reports_router
from app.core.authz import public_operation
from app.core.config import get_settings
from app.core.errors import http_error_handler, unhandled_error_handler, validation_error_handler
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
)
app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_error_handler))
app.add_exception_handler(RequestValidationError, cast(ExceptionHandler, validation_error_handler))
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(farms_router, prefix="/api/v1")
app.include_router(farm_resources_router, prefix="/api/v1")
app.include_router(daily_records_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(feed_stock_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")


@app.get("/health", tags=["health"], dependencies=[Depends(public_operation)])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["health"], dependencies=[Depends(public_operation)])
def readiness() -> dict[str, str]:
    if not database_ready():
        raise HTTPException(status_code=503, detail="Service is not ready")
    return {"status": "ready"}
