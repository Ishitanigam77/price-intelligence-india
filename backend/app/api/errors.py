"""Centralized API exception handling.

Per Phase 2 scope (`DEVELOPMENT_RULES.md` §5), every failure mode returns the same
`app.schemas.common.ErrorResponse` envelope, and no handler ever exposes internal stack traces,
SQL statements, or secrets to the client. Unexpected errors are logged server-side (with full
detail) and returned to the client as a generic, safe message.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.security import sanitize_validation_errors
from app.auth.errors import AuthenticationError, AuthorizationError
from app.domain.exceptions import DomainError
from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised by API routes when a requested resource does not exist.

    Deliberately a plain application-level exception (not an `HTTPException`) so route handlers
    stay free of HTTP-status concerns; `register_exception_handlers` is the single place that
    translates it into a response.
    """

    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__(message)
        self.message = message


class ConflictError(Exception):
    """Raised when a create would violate a uniqueness constraint (e.g. duplicate watchlist)."""

    def __init__(self, message: str = "The resource already exists.") -> None:
        super().__init__(message)
        self.message = message


def _error_response(
    status_code: int, code: str, message: str, fields: list[dict] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, fields=fields))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    """Register every centralized exception handler on the given FastAPI app instance."""

    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _error_response(status.HTTP_404_NOT_FOUND, "not_found", exc.message)

    @app.exception_handler(AuthenticationError)
    async def handle_authentication_error(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        return _error_response(status.HTTP_401_UNAUTHORIZED, "unauthenticated", exc.message)

    @app.exception_handler(AuthorizationError)
    async def handle_authorization_error(request: Request, exc: AuthorizationError) -> JSONResponse:
        return _error_response(status.HTTP_403_FORBIDDEN, "forbidden", exc.message)

    @app.exception_handler(ConflictError)
    async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, "conflict", exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,  # RFC 9110 "Unprocessable Content" (named UNPROCESSABLE_ENTITY pre-Starlette 0.44)
            "validation_error",
            "Request validation failed.",
            fields=sanitize_validation_errors(exc.errors()),
        )

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _error_response(status.HTTP_400_BAD_REQUEST, "domain_error", str(exc))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Preserves FastAPI/Starlette's own HTTPException usage (e.g. 503 from the readiness
        # check) while still returning the common error envelope.
        code = "http_error"
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "unauthenticated"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code = "forbidden"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            code = "not_found"
        elif exc.status_code == status.HTTP_409_CONFLICT:
            code = "conflict"
        elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            code = "service_unavailable"
        return _error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception(
            "Unhandled database error while processing %s %s", request.method, request.url.path
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "database_error",
            "A database error occurred. Please try again later.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred. Please try again later.",
        )
