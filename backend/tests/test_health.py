"""Health endpoint tests.

Dependencies are stubbed on ``app.state`` so the suite never opens a socket.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.health import ComponentHealth, ComponentStatus, aggregate, probe
from app.main import create_app
from app.settings import Settings


class _StubResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


class _StubHttpClient:
    def __init__(self, payload: dict[str, Any] | None = None, fail: bool = False) -> None:
        self._payload = payload or {"status": "ok"}
        self._fail = fail

    async def get(self, url: str, timeout: float | None = None) -> _StubResponse:
        if self._fail:
            raise ConnectionError("image worker unreachable at postgres://u:hunter2@host")
        return _StubResponse(self._payload)

    async def aclose(self) -> None:
        return None


class _StubRedis:
    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    async def ping(self) -> bool:
        if not self._healthy:
            raise ConnectionError("redis://user:hunter2@host refused")
        return True

    async def aclose(self) -> None:
        return None


class _StubConnection:
    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    async def __aenter__(self) -> _StubConnection:
        if not self._healthy:
            raise ConnectionError("postgresql://user:hunter2@host refused")
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, _statement: object) -> _StubConnection:
        return self

    def scalar_one(self) -> int:
        return 1


class _StubEngine:
    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    def connect(self) -> _StubConnection:
        return _StubConnection(self._healthy)

    async def dispose(self) -> None:
        return None


@pytest.fixture
def client_factory(settings: Settings):  # type: ignore[no-untyped-def]
    """Build a client whose app.state holds stubs instead of real clients.

    The lifespan is entered exactly once here; entering it again (for example by
    using the client as a context manager) would rebuild the real engine and
    silently undo the stubbing.
    """
    entered: list[TestClient] = []

    def build(*, db_ok: bool = True, redis_ok: bool = True, worker_ok: bool = True) -> TestClient:
        application = create_app(settings)
        client = TestClient(application, raise_server_exceptions=False)
        client.__enter__()
        entered.append(client)
        application.state.engine = _StubEngine(db_ok)
        application.state.redis = _StubRedis(redis_ok)
        application.state.http_client = _StubHttpClient(fail=not worker_ok)
        return client

    yield build

    for client in entered:
        client.__exit__(None, None, None)


def test_liveness_does_not_touch_dependencies(client_factory) -> None:  # type: ignore[no-untyped-def]
    client = client_factory(db_ok=False, redis_ok=False, worker_ok=False)
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_every_component(client_factory) -> None:  # type: ignore[no-untyped-def]
    response = client_factory().get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["components"]) == {"database", "redis", "image_worker"}


@pytest.mark.parametrize(
    ("kwargs", "failing"),
    [
        ({"db_ok": False}, "database"),
        ({"redis_ok": False}, "redis"),
        ({"worker_ok": False}, "image_worker"),
    ],
)
def test_health_returns_503_when_a_dependency_is_down(  # type: ignore[no-untyped-def]
    client_factory, kwargs: dict[str, bool], failing: str
) -> None:
    response = client_factory(**kwargs).get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "down"
    assert body["components"][failing]["status"] == "down"


def test_health_failure_detail_never_leaks_credentials(client_factory) -> None:  # type: ignore[no-untyped-def]
    response = client_factory(redis_ok=False, db_ok=False, worker_ok=False).get("/api/health")
    assert response.status_code == 503
    assert "hunter2" not in response.text


def test_correlation_id_is_echoed(client_factory) -> None:  # type: ignore[no-untyped-def]
    response = client_factory().get("/api/health/live", headers={"x-correlation-id": "corr-42"})
    assert response.headers["x-correlation-id"] == "corr-42"


def test_correlation_id_is_generated_when_absent(client_factory) -> None:  # type: ignore[no-untyped-def]
    response = client_factory().get("/api/health/live")
    assert len(response.headers["x-correlation-id"]) >= 16


async def test_probe_reports_only_the_error_class() -> None:
    async def boom() -> None:
        raise ConnectionError("postgresql://user:hunter2@host")

    result = await probe(boom)
    assert result.status is ComponentStatus.DOWN
    assert result.detail == "ConnectionError"


def test_aggregate_prefers_the_worst_status() -> None:
    report = aggregate(
        {
            "a": ComponentHealth(status=ComponentStatus.OK),
            "b": ComponentHealth(status=ComponentStatus.DOWN),
        },
        service="api",
        version="0.1.0",
        app_env="local",
    )
    assert report.status is ComponentStatus.DOWN
