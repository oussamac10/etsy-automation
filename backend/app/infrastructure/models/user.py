"""Account ownership and the owner's credential.

Phase 2 stored *who owns what*. Phase 3 adds the single Argon2id password hash
(ADR-0002). ``password_hash`` is nullable so an account can exist before a
password is set — a user in that state cannot authenticate, which is exactly the
behaviour wanted for a half-provisioned account.

Sessions live in their own table (``app/infrastructure/models/auth.py``); a
session column here would make revocation an update on the user row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin

if TYPE_CHECKING:
    from app.infrastructure.models.auth import UserSession
    from app.infrastructure.models.owner_settings import OwnerSettings, ProviderCredential
    from app.infrastructure.models.workflow import ProductWorkflow


class User(UuidMixin, TimestampMixin, Base):
    """The shop owner.

    The MVP has exactly one, but workflows carry an owner reference anyway so
    Phase 3 can enforce ownership and Phase 11 can add tenancy without a
    migration that backfills every row.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    #: Argon2id, encoded with its own parameters and salt. Never the password,
    #: never a reversible transformation of it, and never returned by the API.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflows: Mapped[list[ProductWorkflow]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    settings: Mapped[OwnerSettings | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    provider_credentials: Mapped[list[ProviderCredential]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def can_authenticate(self) -> bool:
        """An account may log in only when it is active and has a password."""
        return self.is_active and self.password_hash is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id} {self.email}>"
