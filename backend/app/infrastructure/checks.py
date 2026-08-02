"""Concrete dependency probes for PostgreSQL, Redis and the image worker."""

from __future__ import annotations

import httpx
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.health import ComponentHealth, probe


async def check_database(engine: AsyncEngine) -> ComponentHealth:
    """`SELECT 1` over a pooled connection."""

    async def run() -> None:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            if result.scalar_one() != 1:
                raise RuntimeError("unexpected result")

    return await probe(run)


async def check_redis(client: aioredis.Redis) -> ComponentHealth:
    async def run() -> None:
        if not await client.ping():
            raise RuntimeError("no pong")

    return await probe(run)


async def check_image_worker(client: httpx.AsyncClient, base_url: str) -> ComponentHealth:
    """Ask the Node/Sharp service for its own liveness."""

    async def run() -> None:
        response = await client.get(f"{base_url.rstrip('/')}/health/live", timeout=3.0)
        response.raise_for_status()
        if response.json().get("status") != "ok":
            raise RuntimeError("image worker not ok")

    return await probe(run)
