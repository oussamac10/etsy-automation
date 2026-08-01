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
from collections.abc import AsyncIterator
from pathlib import Path

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
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
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
