"""Request-scoped dependencies: the unit of work, the identity and CSRF.

This is the only place a route learns who is calling. A handler that wants an
owner ID asks for :data:`CurrentUser`; it cannot read one from a request body,
because no schema offers one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request

from app.application import auth as auth_use_cases
from app.application.unit_of_work import UnitOfWork
from app.domain.errors import CsrfValidationError, NotAuthenticatedError
from app.infrastructure.models import User
from app.infrastructure.security import (
    CredentialCipher,
    EncryptionConfigurationError,
    tokens_equal,
)
from app.settings import Settings

#: Header the browser echoes the CSRF cookie in. Lowercase; Starlette's header
#: lookup is case-insensitive.
CSRF_HEADER = "x-csrf-token"
CSRF_COOKIE_NAME = "etsy_csrf"

#: Methods that change state and therefore need the CSRF token. A safe method
#: with a stolen cookie can read, which SameSite=Lax already restricts.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


async def get_uow(request: Request) -> AsyncIterator[UnitOfWork]:
    """One unit of work per request, built from the app's session factory.

    The dependency owns the lifecycle so no handler repeats it: the session is
    opened before the handler runs and closed after it returns. Whether the work
    is committed stays with the use case; an exception leaving the handler is
    re-raised inside this generator, so ``__aexit__`` rolls back before closing.
    """
    async with UnitOfWork(request.app.state.session_factory) as uow:
        yield uow


UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_credential_cipher(request: Request) -> CredentialCipher | None:
    """The configured cipher, or ``None`` when the key is unusable.

    Built once at startup. Returning ``None`` rather than raising here means a
    broken encryption key does not take down the whole API — only the endpoints
    that actually need to encrypt something, which answer 503.
    """
    cipher: CredentialCipher | None = getattr(request.app.state, "credential_cipher", None)
    return cipher


CipherDep = Annotated[CredentialCipher | None, Depends(get_credential_cipher)]


def build_credential_cipher(settings: Settings) -> CredentialCipher | None:
    """Startup helper. Never raises: a bad key must not hide behind a stack trace."""
    try:
        previous = settings.encryption_key_previous
        return CredentialCipher(
            settings.encryption_key.get_secret_value(),
            key_version=settings.encryption_key_version,
            previous_key=previous.get_secret_value() if previous is not None else None,
            previous_key_version=settings.encryption_key_previous_version,
        )
    except EncryptionConfigurationError:
        return None


async def get_current_user(request: Request, uow: UowDep) -> User:
    """Resolve the session cookie to a user, enforcing CSRF on mutations.

    Order matters: authentication first, then CSRF. A request with no session at
    all should hear "log in", not "your CSRF token is wrong".
    """
    settings = get_app_settings(request)
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise NotAuthenticatedError

    session, user = await auth_use_cases.resolve_session(uow, token)

    if request.method in UNSAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER)
        # The token is compared against the session row, not just against a
        # second cookie: a subdomain that can set cookies cannot forge this.
        if not supplied or not tokens_equal(supplied, session.csrf_token):
            raise CsrfValidationError

    # `resolve_session` updated `last_seen_at` in the session; commit it here so
    # a read-only handler that never commits does not lose the touch.
    await uow.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
