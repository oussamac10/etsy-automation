"""The request-scoped unit of work dependency.

``get_uow`` owns the session lifecycle so no handler repeats it. These tests
pin the three things that guarantees: the session is always closed, a commit
only happens because a use case asked for one, and an exception leaving the
handler rolls back before the close.

A stub session keeps this a unit test — the behaviour under test is the
dependency's exit path, not SQL.
"""

from __future__ import annotations

import inspect
from typing import Any

import httpx
from fastapi import FastAPI

from app.api.dependencies import UowDep, get_uow
from app.api.problems import register_exception_handlers
from app.domain.errors import EntityNotFoundError


class StubSession:
    """Records the calls ``UnitOfWork`` makes on its session."""

    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")

    async def close(self) -> None:
        self._log.append("close")


class StubLogger:
    """Stands in for the app logger the unhandled-exception handler uses."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def exception(self, event: str, **_: Any) -> None:
        self.events.append(event)


class StubSessionFactory:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.sessions = 0

    def __call__(self) -> StubSession:
        self.sessions += 1
        return StubSession(self.log)


def _app(factory: StubSessionFactory, logger: StubLogger | None = None) -> FastAPI:
    """A minimal app using the real dependency and the real error handlers."""
    app = FastAPI()
    app.state.session_factory = factory
    app.state.logger = logger if logger is not None else StubLogger()
    register_exception_handlers(app)

    @app.get("/commit")
    async def commit_route(uow: UowDep) -> dict[str, bool]:
        # Repositories are bound, which only happens inside ``__aenter__``.
        assert uow.workflows is not None
        await uow.commit()
        return {"committed": True}

    @app.get("/read-only")
    async def read_only_route(uow: UowDep) -> dict[str, bool]:
        return {"committed": False}

    @app.get("/domain-error")
    async def domain_error_route(uow: UowDep) -> dict[str, bool]:
        raise EntityNotFoundError("ProductWorkflow", "00000000-0000-0000-0000-000000000000")

    @app.get("/boom")
    async def boom_route(uow: UowDep) -> dict[str, bool]:
        raise RuntimeError("handler exploded")

    return app


async def _get(app: FastAPI, path: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, **kwargs)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def test_get_uow_is_an_async_generator() -> None:
    """A plain ``return`` would hand handlers an un-entered unit of work.

    That is the regression this change removed: the lifecycle belongs to the
    dependency, so the function must yield.
    """
    assert inspect.isasyncgenfunction(get_uow)


async def test_session_is_closed_after_a_successful_request() -> None:
    factory = StubSessionFactory()
    response = await _get(_app(factory), "/commit")

    assert response.status_code == 200
    assert factory.sessions == 1
    # Committed by the use case, then closed exactly once by the dependency.
    assert factory.log == ["commit", "close"]


async def test_a_request_that_never_commits_writes_nothing() -> None:
    """Read paths must not commit on the handler's behalf."""
    factory = StubSessionFactory()
    response = await _get(_app(factory), "/read-only")

    assert response.status_code == 200
    assert factory.log == ["close"]


async def test_a_domain_error_rolls_back_before_closing() -> None:
    """The error still becomes a problem response, and nothing is left open."""
    factory = StubSessionFactory()
    response = await _get(_app(factory), "/domain-error")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert factory.log == ["rollback", "close"]


async def test_an_unexpected_exception_rolls_back_before_the_500() -> None:
    """The generic 500 handler runs *after* the unit of work has rolled back."""
    factory = StubSessionFactory()
    logger = StubLogger()

    # Starlette re-raises after sending the 500 so the server can log it; the
    # transport is told not to, because the response is what is under test.
    response = await _get(_app(factory, logger), "/boom", raise_app_exceptions=False)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    # The handler's message never reaches the client.
    assert "exploded" not in response.text
    assert logger.events == ["unhandled_exception"]
    assert factory.log == ["rollback", "close"]


async def test_each_request_gets_its_own_session() -> None:
    factory = StubSessionFactory()
    app = _app(factory)

    await _get(app, "/commit")
    await _get(app, "/commit")

    assert factory.sessions == 2
    assert factory.log == ["commit", "close", "commit", "close"]
