"""Integration fixtures: a real PostgreSQL database per test session.

These tests need PostgreSQL because the things they check — enum types, check
constraints, unique indexes, cascade behaviour and compare-and-set updates — are
database behaviour, not Python behaviour. SQLite would prove nothing about them.

Point ``TEST_DATABASE_URL`` at a disposable database. Compose provides one:

    TEST_DATABASE_URL=postgresql+asyncpg://etsy:etsy_local_password@localhost:5432/etsy_test

The whole schema is created from the Alembic migrations, not from
``metadata.create_all``, so every run also proves the migration works.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.infrastructure.database import create_engine, create_session_factory
from app.infrastructure.models import User

API_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://etsy:etsy_local_password@localhost:5432/etsy_test"


def _database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


#: Skips the whole package when no database is reachable, with a message that
#: says how to get one — a silent skip would look like a pass.
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def database_url() -> str:
    return _database_url()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(database_url: str) -> None:
    """Run the migrations once per session against a clean database."""
    import asyncio

    import sqlalchemy

    async def _reachable() -> bool:
        engine = create_engine(database_url)
        try:
            async with engine.connect() as connection:
                await connection.execute(sqlalchemy.text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    if not asyncio.run(_reachable()):
        pytest.skip(
            f"No PostgreSQL at {database_url.rsplit('@', 1)[-1]}. "
            "Start one with `docker compose up -d postgres` and create the "
            "test database, or set TEST_DATABASE_URL.",
            allow_module_level=True,
        )

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    os.environ["DATABASE_URL"] = database_url

    # Down to base first: a leftover schema from an earlier run would hide a
    # migration that only works on an empty database.
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[object]:
    engine = create_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine: object) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)  # type: ignore[arg-type]


@pytest.fixture
async def clean_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Truncate every table between tests.

    TRUNCATE ... CASCADE rather than dropping and recreating: it keeps the enum
    types and constraints the migration built, which are the point of these
    tests.
    """
    import sqlalchemy

    from app.infrastructure.models.base import metadata

    async with session_factory() as session:
        table_names = ", ".join(
            f'"{table}"' for table in metadata.tables if table != "alembic_version"
        )
        await session.execute(sqlalchemy.text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        await session.commit()
    yield


@pytest.fixture
async def uow(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(session_factory) as unit:
        yield unit


@pytest.fixture
async def owner(uow: UnitOfWork) -> User:
    user = await uow.users.add(email="owner@example.invalid", display_name="Owner")
    await uow.commit()
    return user


# --- Authenticated HTTP clients (Phase 3) ----------------------------------

#: Two accounts, so every ownership rule can be tested against a real second
#: person rather than a hypothetical one.
OWNER_EMAIL = "api-owner@example.invalid"
OTHER_EMAIL = "api-other@example.invalid"
TEST_PASSWORD = "integration-test-password"


@pytest.fixture
async def api_app(
    settings: object,
    session_factory: async_sessionmaker[AsyncSession],
    engine: object,
    clean_database: None,
) -> AsyncIterator[object]:
    """The real app, wired to the test database.

    ``ASGITransport`` skips the lifespan, so the session factory and the
    credential cipher are set here instead.
    """
    import httpx
    import redis.asyncio as aioredis

    from app.api.dependencies import build_credential_cipher
    from app.main import create_app
    from app.providers.s3 import S3ObjectStorage
    from app.providers.telegram import FakeTelegramGateway

    app = create_app(settings)  # type: ignore[arg-type]
    app.state.session_factory = session_factory
    app.state.credential_cipher = build_credential_cipher(settings)  # type: ignore[arg-type]
    app.state.engine = engine
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[attr-defined]
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.telegram_gateway = FakeTelegramGateway()
    app.state.storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    yield app

    await app.state.redis.aclose()
    await app.state.http_client.aclose()


@pytest.fixture
async def accounts(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> dict[str, uuid.UUID]:
    """Create both test accounts with real Argon2 hashes."""
    from app.application.auth import create_owner

    async with UnitOfWork(session_factory) as unit:
        first = await create_owner(
            unit, email=OWNER_EMAIL, display_name="API Owner", password=TEST_PASSWORD
        )
        second = await create_owner(
            unit, email=OTHER_EMAIL, display_name="Other Owner", password=TEST_PASSWORD
        )
        await unit.commit()
        return {"owner": first.id, "other": second.id}


async def open_client(app: object, email: str | None = None) -> httpx.AsyncClient:
    """An HTTP client, signed in when an email is given.

    The CSRF token is copied from the login response into a default header,
    which is exactly what the browser client does.
    """
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    if email is not None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, response.text
        client.headers["x-csrf-token"] = client.cookies["etsy_csrf"]
    return client


@pytest.fixture
async def anon_client(api_app: object) -> AsyncIterator[httpx.AsyncClient]:
    client = await open_client(api_app)
    yield client
    await client.aclose()


@pytest.fixture
async def client(
    api_app: object, accounts: dict[str, uuid.UUID]
) -> AsyncIterator[httpx.AsyncClient]:
    """Signed in as the first owner."""
    signed_in = await open_client(api_app, OWNER_EMAIL)
    yield signed_in
    await signed_in.aclose()


@pytest.fixture
async def other_client(
    api_app: object, accounts: dict[str, uuid.UUID]
) -> AsyncIterator[httpx.AsyncClient]:
    """Signed in as a *different* owner, for isolation tests."""
    signed_in = await open_client(api_app, OTHER_EMAIL)
    yield signed_in
    await signed_in.aclose()
