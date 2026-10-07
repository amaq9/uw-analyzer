"""Standard error object (PRD section 7): code, safe message, correlation ID, retryable flag and
optional field errors. Never exposes secrets, stack traces, tokens or submitted values."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.audit.recorder import correlation_id_of

logger = logging.getLogger("uw.errors")

_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
}
_RETRYABLE = {429, 502, 503, 504}


class FieldError(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: str
    retryable: bool
    field_errors: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# Documented on every route so the OpenAPI contract describes the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not signed in, or the token is invalid."},
    403: {"model": ErrorResponse, "description": "Signed in but not permitted."},
    404: {"model": ErrorResponse, "description": "Not found (or belongs to another tenant)."},
    422: {"model": ErrorResponse, "description": "The request was malformed."},
}


def _response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    field_errors: list[FieldError] | None = None,
) -> JSONResponse:
    correlation_id = correlation_id_of(request)
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            correlation_id=correlation_id,
            retryable=retryable,
            field_errors=field_errors,
        )
    )
    response = JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))
    response.headers["X-Request-ID"] = correlation_id
    return response


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "http_error")
        message = (
            exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        )
        response = _response(
            request, exc.status_code, code, message, retryable=exc.status_code in _RETRYABLE
        )
        for name, value in (exc.headers or {}).items():
            response.headers[name] = value
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Only the location and the rule that failed. Never echo the submitted value.
        fields = [
            FieldError(
                field=".".join(str(part) for part in error["loc"][1:])
                or (str(error["loc"][0]) if error["loc"] else "body"),
                message=str(error["msg"]).removeprefix("Value error, "),
            )
            for error in exc.errors()
        ]
        return _response(
            request,
            422,
            "validation_error",
            "Some fields are not valid. Nothing was saved. Fix them and try again.",
            field_errors=fields,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_error type=%s correlation_id=%s",
            type(exc).__name__,
            correlation_id_of(request),
            exc_info=exc,
        )
        return _response(
            request,
            500,
            "internal_error",
            "An unexpected error occurred. If this was a change, check before repeating it. "
            "Quote the correlation ID if it continues.",
            retryable=False,
        )
