"""Errors are RFC 9457 problem documents and never leak internals."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

router = APIRouter()


@router.get("/boom")
async def boom() -> None:
    raise RuntimeError("connection string postgresql://u:hunter2@host failed")


def test_unknown_route_returns_problem_details(settings: Settings) -> None:
    client = TestClient(create_app(settings), raise_server_exceptions=False)
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["type"].endswith("/http-error")
    assert body["instance"] == "/api/does-not-exist"


def test_unhandled_exception_is_generic(settings: Settings) -> None:
    application = create_app(settings)
    application.include_router(router, prefix="/api")
    client = TestClient(application, raise_server_exceptions=False)

    response = client.get("/api/boom")
    assert response.status_code == 500
    assert "hunter2" not in response.text
    assert response.json()["detail"] == "The request could not be completed."


def test_problem_carries_the_correlation_id(settings: Settings) -> None:
    client = TestClient(create_app(settings), raise_server_exceptions=False)
    response = client.get("/api/nope", headers={"x-correlation-id": "corr-7"})
    assert response.json()["correlation_id"] == "corr-7"
