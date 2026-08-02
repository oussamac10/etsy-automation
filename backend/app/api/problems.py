"""RFC 9457 problem details.

Every error response uses this shape so clients have one contract, and internal
exception text never reaches the browser.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import (
    AuthenticationFailedError,
    BudgetExceededError,
    ConcurrentModificationError,
    CredentialConfigurationError,
    CsrfValidationError,
    DomainError,
    EntityNotFoundError,
    ImmutableFieldError,
    InvalidIdeaModeError,
    NotAuthenticatedError,
)
from app.domain.owner_settings import BudgetRelationError
from app.domain.workflow import (
    GateNotApprovedError,
    GateNotSatisfiedError,
    IllegalTransitionError,
)

PROBLEM_CONTENT_TYPE = "application/problem+json"
PROBLEM_BASE_URI = "https://etsy-automation.invalid/problems"


class Problem(BaseModel):
    """RFC 9457 problem detail document."""

    type: str = Field(default=f"{PROBLEM_BASE_URI}/about:blank")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    correlation_id: str | None = None


def problem_response(
    *,
    title: str,
    status_code: int,
    detail: str | None = None,
    problem_type: str = "about:blank",
    instance: str | None = None,
    correlation_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body = Problem(
        type=f"{PROBLEM_BASE_URI}/{problem_type}",
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        correlation_id=correlation_id,
    ).model_dump()
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_CONTENT_TYPE)


#: Domain errors mapped to a status code and a problem type. Everything else
#: falls through to the generic 500 handler, so an unmapped rule cannot leak its
#: message to a client by accident.
DOMAIN_ERROR_STATUS: dict[type[Exception], tuple[int, str]] = {
    EntityNotFoundError: (status.HTTP_404_NOT_FOUND, "not-found"),
    ImmutableFieldError: (status.HTTP_409_CONFLICT, "immutable-field"),
    ConcurrentModificationError: (status.HTTP_409_CONFLICT, "concurrent-modification"),
    GateNotSatisfiedError: (status.HTTP_409_CONFLICT, "gate-not-satisfied"),
    GateNotApprovedError: (status.HTTP_409_CONFLICT, "gate-not-approved"),
    IllegalTransitionError: (status.HTTP_409_CONFLICT, "illegal-transition"),
    InvalidIdeaModeError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid-idea-mode"),
    BudgetExceededError: (status.HTTP_409_CONFLICT, "budget-exceeded"),
    # Both authentication failures are 401 with the same shape. A different
    # status or message for "unknown account" would be an enumeration oracle.
    AuthenticationFailedError: (status.HTTP_401_UNAUTHORIZED, "authentication-failed"),
    NotAuthenticatedError: (status.HTTP_401_UNAUTHORIZED, "not-authenticated"),
    CsrfValidationError: (status.HTTP_403_FORBIDDEN, "csrf-failed"),
    # 503, not 500: the request was fine, the server is misconfigured, and the
    # owner can fix it by setting a valid ENCRYPTION_KEY.
    CredentialConfigurationError: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "encryption-unavailable",
    ),
}


def _domain_error_mapping(exc: Exception) -> tuple[int, str] | None:
    for error_type, mapping in DOMAIN_ERROR_STATUS.items():
        if isinstance(exc, error_type):
            return mapping
    return None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        """Domain rules become problem details.

        The message is safe to show: these errors are written for the person who
        triggered them and never contain a provider payload or a connection
        string. Anything not in the mapping is re-raised so the generic handler
        can hide it instead of guessing.
        """
        mapping = _domain_error_mapping(exc)
        if mapping is None:
            raise exc
        status_code, problem_type = mapping

        extra: dict[str, Any] = {}
        if isinstance(exc, ConcurrentModificationError):
            extra = {
                "expected_version": exc.expected_version,
                "actual_version": exc.actual_version,
            }
        elif isinstance(exc, IllegalTransitionError):
            extra = {
                "current_state": exc.current.value,
                "requested_state": exc.requested.value,
            }
        elif isinstance(exc, GateNotSatisfiedError | GateNotApprovedError):
            extra = {"gate": exc.gate.value, "current_state": exc.current.value}

        return problem_response(
            title=type(exc).__name__.removesuffix("Error"),
            status_code=status_code,
            detail=str(exc),
            problem_type=problem_type,
            instance=str(request.url.path),
            correlation_id=getattr(request.state, "correlation_id", None),
            extra=extra,
        )

    @app.exception_handler(BudgetRelationError)
    async def _budget_relation(request: Request, exc: BudgetRelationError) -> JSONResponse:
        """A cross-field settings rule.

        Not a ``DomainError``: it is a ``ValueError`` raised by the pure domain
        module so it can also be used from a validator. It still deserves the
        same 422 shape as any other rejected value.
        """
        return problem_response(
            title="Invalid budget combination",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
            problem_type="invalid-budget-relation",
            instance=str(request.url.path),
            correlation_id=getattr(request.state, "correlation_id", None),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem_response(
            title=str(exc.detail),
            status_code=exc.status_code,
            problem_type="http-error",
            instance=str(request.url.path),
            correlation_id=getattr(request.state, "correlation_id", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(
            title="Request validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            problem_type="validation-error",
            instance=str(request.url.path),
            correlation_id=getattr(request.state, "correlation_id", None),
            extra={
                "errors": [
                    {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                    for error in exc.errors()
                ]
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # The message is intentionally generic: an unhandled exception can carry
        # a DSN, a prompt or a token. Details go to the structured log only.
        request.app.state.logger.exception(
            "unhandled_exception",
            path=str(request.url.path),
            error_type=type(exc).__name__,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
        return problem_response(
            title="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The request could not be completed.",
            problem_type="internal-error",
            instance=str(request.url.path),
            correlation_id=getattr(request.state, "correlation_id", None),
        )
