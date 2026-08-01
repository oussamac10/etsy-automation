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


def register_exception_handlers(app: FastAPI) -> None:
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
