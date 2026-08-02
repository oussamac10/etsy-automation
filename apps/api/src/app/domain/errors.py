"""Domain errors.

These are raised by the domain and use-case layers and mapped to problem
details at the HTTP boundary (``app/api/problems.py``). They carry structured
attributes rather than pre-formatted messages so a route can build a useful
response without parsing a string.
"""

from __future__ import annotations

from uuid import UUID


class DomainError(Exception):
    """Base class for every rule the domain enforces."""


class EntityNotFoundError(DomainError):
    """A referenced entity does not exist. Maps to 404."""

    def __init__(self, entity: str, entity_id: UUID | str) -> None:
        super().__init__(f"{entity} {entity_id} was not found.")
        self.entity = entity
        self.entity_id = str(entity_id)


class ImmutableFieldError(DomainError):
    """An append-only or write-once value was modified. Maps to 409.

    The original idea text is the main case: it is the owner's own words, and a
    later revision must be stored as a new row rather than overwriting history.
    """

    def __init__(self, entity: str, field: str, reason: str = "") -> None:
        detail = f" {reason}" if reason else ""
        super().__init__(f"{entity}.{field} is immutable and cannot be modified.{detail}")
        self.entity = entity
        self.field = field
        self.reason = reason


class ConcurrentModificationError(DomainError):
    """A compare-and-set update lost. Maps to 409.

    Raised when a workflow's version has moved since the caller read it, which
    means someone else changed it and the caller's decision may be stale.
    """

    def __init__(self, entity: str, entity_id: UUID | str, expected: int, actual: int) -> None:
        super().__init__(
            f"{entity} {entity_id} was modified concurrently: "
            f"expected version {expected}, found {actual}."
        )
        self.entity = entity
        self.entity_id = str(entity_id)
        self.expected_version = expected
        self.actual_version = actual


class InvalidIdeaModeError(DomainError):
    """The submitted input does not match the workflow's idea mode. Maps to 422."""

    def __init__(self, mode: str, reason: str) -> None:
        super().__init__(f"Idea mode {mode}: {reason}")
        self.mode = mode
        self.reason = reason


class AuthenticationFailedError(DomainError):
    """Login was refused. Maps to 401.

    Carries no structured attribute and one fixed message on purpose: a wrong
    password, an unknown email and a disabled account must be indistinguishable
    to the caller, or the endpoint becomes an account-enumeration oracle.
    """

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class NotAuthenticatedError(DomainError):
    """A protected operation was attempted with no valid session. Maps to 401."""

    def __init__(self, reason: str = "Authentication is required.") -> None:
        super().__init__(reason)


class CsrfValidationError(DomainError):
    """A cookie-authenticated mutation arrived without a matching CSRF token.

    Maps to 403. Separate from :class:`NotAuthenticatedError` because the client
    fix is different: re-send the token, not log in again.
    """

    def __init__(self) -> None:
        super().__init__("Missing or invalid CSRF token.")


class CredentialConfigurationError(DomainError):
    """A provider credential could not be encrypted or decrypted. Maps to 503.

    Raised when ``ENCRYPTION_KEY`` is missing, too short, or does not match the
    key version a stored row was written with. Never contains the key or the
    credential.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BudgetExceededError(DomainError):
    """A projected cost would breach a budget ceiling. Maps to 409."""

    def __init__(self, scope: str, limit_minor: int, projected_minor: int, currency: str) -> None:
        super().__init__(
            f"{scope} budget of {limit_minor} {currency} minor units would be "
            f"exceeded by a projected {projected_minor}."
        )
        self.scope = scope
        self.limit_minor = limit_minor
        self.projected_minor = projected_minor
        self.currency = currency
