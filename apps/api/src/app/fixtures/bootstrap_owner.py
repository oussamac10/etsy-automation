"""Provision the single owner account.

There is no public registration route (ADR-0002), so a real deployment gets its
owner from here::

    BOOTSTRAP_OWNER_EMAIL=me@example.com \
    BOOTSTRAP_OWNER_PASSWORD='...' \
    python -m app.fixtures.bootstrap_owner

The password comes from the environment and is never echoed, logged or written
to a file. Re-running is safe: an existing account is left exactly as it is,
including its password, so this cannot be used to take an account over.
"""

from __future__ import annotations

import asyncio
import os

from app.application.auth import create_owner
from app.application.unit_of_work import UnitOfWork
from app.infrastructure.database import create_engine, create_session_factory
from app.settings import get_settings

MIN_PASSWORD_LENGTH = 12


async def _main() -> None:
    email = os.environ.get("BOOTSTRAP_OWNER_EMAIL", "").strip()
    password = os.environ.get("BOOTSTRAP_OWNER_PASSWORD", "")
    display_name = os.environ.get("BOOTSTRAP_OWNER_NAME", "").strip() or "Shop owner"

    if not email or "@" not in email:
        raise SystemExit("BOOTSTRAP_OWNER_EMAIL must be set to an email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"BOOTSTRAP_OWNER_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    engine = create_engine(get_settings().database_url)
    try:
        async with UnitOfWork(create_session_factory(engine)) as uow:
            existing = await uow.users.get_by_email(email)
            user = await create_owner(
                uow, email=email, display_name=display_name, password=password
            )
            await uow.commit()
        # The address is the operator's own input; the password is not printed.
        print(f"{'already exists' if existing else 'created'}: {user.id} {email}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
