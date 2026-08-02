"""Re-encrypt stored provider credentials under a new ``ENCRYPTION_KEY``.

Rotation is three steps, and the application stays up throughout::

    # 1. Point ENCRYPTION_KEY at the new value, move the old one aside and
    #    bump the version:
    #      ENCRYPTION_KEY=<new>
    #      ENCRYPTION_KEY_VERSION=2
    #      ENCRYPTION_KEY_PREVIOUS=<old>
    #      ENCRYPTION_KEY_PREVIOUS_VERSION=1
    # 2. Re-encrypt every row still on the old key:
    python -m app.rotate_encryption_key
    # 3. Unset ENCRYPTION_KEY_PREVIOUS and ENCRYPTION_KEY_PREVIOUS_VERSION.

Between steps 1 and 3 both keys can decrypt, so nothing is lost. Step 2 is safe
to re-run and prints only a count — never a key or a credential.
"""

from __future__ import annotations

import asyncio

from app.api.dependencies import build_credential_cipher
from app.application.owner_settings import rotate_credential_keys
from app.application.unit_of_work import UnitOfWork
from app.infrastructure.database import create_engine, create_session_factory
from app.settings import get_settings


async def _main() -> None:
    settings = get_settings()
    cipher = build_credential_cipher(settings)
    if cipher is None:
        raise SystemExit("ENCRYPTION_KEY is missing or invalid; nothing was changed.")

    engine = create_engine(settings.database_url)
    try:
        async with UnitOfWork(create_session_factory(engine)) as uow:
            rotated = await rotate_credential_keys(uow, cipher=cipher)
        print(f"re-encrypted {rotated} credential(s) under key version {cipher.key_version}")
        if rotated and settings.encryption_key_previous is not None:
            print("Now unset ENCRYPTION_KEY_PREVIOUS and ENCRYPTION_KEY_PREVIOUS_VERSION.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
