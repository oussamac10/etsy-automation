"""Authentication use cases (ADR-0002).

Login mints a server-side session; the route turns the returned token into a
cookie. Keeping the cookie decision in the route means these functions are
testable without an HTTP layer, and a future OIDC adapter would replace
:func:`login` alone.

Nothing here logs the email, the password or the token. The audit trail records
*that* a login happened, never the credential that made it happen.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import (
    AuthenticationFailedError,
    CsrfValidationError,
    NotAuthenticatedError,
)
from app.infrastructure.models import User, UserSession
from app.infrastructure.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    tokens_equal,
    verify_password,
)

#: A user agent is stored for the owner's own review, not for authorisation.
#: Truncated so a hostile header cannot bloat a row.
MAX_USER_AGENT_LENGTH = 400


@dataclass(frozen=True, slots=True)
class LoginResult:
    """What the route needs to set cookies. The token exists only in transit."""

    session_token: str
    csrf_token: str
    expires_at: datetime
    user: User


def _now() -> datetime:
    return datetime.now(UTC)


async def login(
    uow: UnitOfWork,
    *,
    email: str,
    password: str,
    session_ttl_hours: int,
    user_agent: str | None = None,
) -> LoginResult:
    """Verify a password and open a session.

    Every failure raises the same :class:`AuthenticationFailedError` with the
    same message, and the password is verified even when the user does not
    exist, so the endpoint cannot be used to discover which addresses have
    accounts.
    """
    user = await uow.users.get_by_email(email)
    password_ok = verify_password(user.password_hash if user else None, password)

    if user is None or not password_ok or not user.is_active:
        # The audit row records the attempt without the address that was tried:
        # a failed-login log full of guessed emails is its own small leak.
        await uow.audit.record(
            action=AuditAction.LOGIN_FAILED,
            entity_type="User",
            entity_id=user.id if user is not None else None,
            actor="anonymous",
            summary="Login failed",
            metadata={"reason": _failure_reason(user, password_ok)},
        )
        await uow.commit()
        raise AuthenticationFailedError

    # Argon2 parameters can change between releases; re-hash on the next
    # successful login rather than forcing a password reset.
    if user.password_hash is not None and needs_rehash(user.password_hash):
        await uow.users.set_password_hash(user, hash_password(password))

    now = _now()
    token = generate_session_token()
    csrf_token = generate_session_token()[:64]
    session = await uow.sessions.create(
        user_id=user.id,
        token_hash=hash_session_token(token),
        csrf_token=csrf_token,
        expires_at=now + timedelta(hours=session_ttl_hours),
        user_agent=(user_agent or "")[:MAX_USER_AGENT_LENGTH] or None,
    )
    await uow.audit.record(
        action=AuditAction.LOGIN_SUCCEEDED,
        entity_type="User",
        entity_id=user.id,
        actor=str(user.id),
        summary="Owner signed in",
        metadata={"session_id": str(session.id)},
    )
    await uow.commit()
    return LoginResult(
        session_token=token,
        csrf_token=csrf_token,
        expires_at=session.expires_at,
        user=user,
    )


def _failure_reason(user: User | None, password_ok: bool) -> str:
    """A reason for the audit log only. It is never returned to the client."""
    if user is None:
        return "unknown_account"
    if not password_ok:
        return "bad_password"
    return "inactive_account"


async def resolve_session(uow: UnitOfWork, token: str) -> tuple[UserSession, User]:
    """Turn a cookie value into an authenticated identity.

    Raises :class:`NotAuthenticatedError` for a token that is unknown, revoked,
    expired, or attached to a user who has since been disabled. All four are the
    same 401 to the caller.
    """
    session = await uow.sessions.get_by_token_hash(hash_session_token(token))
    if session is None:
        raise NotAuthenticatedError("Session not found.")

    now = _now()
    if not session.is_usable(now):
        raise NotAuthenticatedError("Session has expired or been revoked.")

    user = session.user
    if not user.is_active:
        # Disabling an account must take effect immediately, not at expiry.
        raise NotAuthenticatedError("Account is disabled.")

    await uow.sessions.touch(session, now=now)
    return session, user


async def logout(uow: UnitOfWork, token: str, *, csrf_token: str | None = None) -> bool:
    """Revoke the session behind a token. Idempotent.

    Returns whether a live session was actually ended, so a caller can tell the
    difference without that difference reaching the HTTP status — logout always
    succeeds from the client's point of view.

    A *live* session is only revoked when ``csrf_token`` matches it. A dead or
    unknown token needs no protection: there is nothing left to revoke.
    """
    session = await uow.sessions.get_by_token_hash(hash_session_token(token))
    if session is None:
        return False

    now = _now()
    was_live = session.is_usable(now)
    if was_live and not (csrf_token and tokens_equal(csrf_token, session.csrf_token)):
        raise CsrfValidationError

    await uow.sessions.revoke(session, now=now)
    if was_live:
        await uow.audit.record(
            action=AuditAction.LOGOUT,
            entity_type="User",
            entity_id=session.user_id,
            actor=str(session.user_id),
            summary="Owner signed out",
            metadata={"session_id": str(session.id)},
        )
    await uow.commit()
    return was_live


async def create_owner(
    uow: UnitOfWork,
    *,
    email: str,
    display_name: str,
    password: str,
    user_id: uuid.UUID | None = None,
) -> User:
    """Provision an owner account.

    There is no public registration route: the MVP has exactly one owner
    (ADR-0002). This is called by the bootstrap command and the development
    fixtures, both of which take the password from outside the repository.
    """
    existing = await uow.users.get_by_email(email)
    if existing is not None:
        return existing

    user = await uow.users.add(
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        # Fixtures pin IDs so tests have something stable to assert on.
        user_id=user_id,
    )
    await uow.audit.record(
        action=AuditAction.ENTITY_CREATED,
        entity_type="User",
        entity_id=user.id,
        actor="system",
        summary="Owner account provisioned",
    )
    return user
