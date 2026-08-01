"""Container health check for the Dramatiq worker.

The worker speaks no HTTP, so readiness is proven by reaching the broker the
process depends on. Exits 0 when healthy, 1 otherwise.
"""

from __future__ import annotations

import sys

import redis

from app.settings import get_settings


def main() -> int:
    settings = get_settings()
    client: redis.Redis = redis.Redis.from_url(
        settings.redis_url, socket_connect_timeout=3, socket_timeout=3
    )
    try:
        return 0 if client.ping() else 1
    except Exception as exc:  # deliberately broad: a health check reports, never raises
        # Only the class name: a Redis URL can contain a password.
        sys.stderr.write(f"worker health check failed: {type(exc).__name__}\n")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
