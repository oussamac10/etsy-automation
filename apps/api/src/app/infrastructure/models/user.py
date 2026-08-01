"""Account ownership foundation.

Phase 2 stores *who owns what*. It stores no credential: there is no password
hash, no session and no token column here. Authentication arrives in Phase 3 and
will add its own columns and tables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin

if TYPE_CHECKING:
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

    workflows: Mapped[list[ProductWorkflow]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id} {self.email}>"
