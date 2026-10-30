from collections.abc import Mapping
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: object = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = str(uuid4())
    return JSONResponse(
        status_code=status_code,
        headers={**(headers or {}), "X-Request-ID": request_id},
        content={
            "error": {
                "code": code,
                "message": message,
                "field_errors": field_errors or {},
                "request_id": request_id,
            }
        },
    )


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }.get(exc.status_code, "REQUEST_FAILED")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=exc.headers,
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(item) for item in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        field_errors=errors,
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid4())
    logger.exception(
        "unhandled_request_error", request_id=request_id, error_type=type(exc).__name__
    )
    return JSONResponse(
        status_code=500,
        headers={"X-Request-ID": request_id},
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "field_errors": {},
                "request_id": request_id,
            }
        },
    )
