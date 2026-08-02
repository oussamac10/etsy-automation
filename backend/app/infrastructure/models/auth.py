"""Server-side sessions (ADR-0002).

The session is the record; the cookie only carries a pointer to it. That is the
whole reason for a table rather than a JWT: logging out, or revoking every
session after a password change, is a write here instead of a token blocklist
bolted onto a stateless scheme.

The token itself is never stored. ``token_hash`` holds SHA-256 of the value the
browser holds, so a database dump cannot be replayed as a live session.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.models.base import (
    Base,
    CreatedAtMixin,
    UuidMixin,
    timestamp_column,
    utc_now,
)

if TYPE_CHECKING:
    from app.infrastructure.models.user import User


class UserSession(UuidMixin, CreatedAtMixin, Base):
    """One authenticated browser session.

    Append-mostly: rows are created at login and revoked (never deleted) at
    logout, so the audit trail and the session table tell the same story.
    ``last_seen_at`` is the one mutable column, which is why this uses
    :class:`CreatedAtMixin` and not the full timestamp mixin.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: SHA-256 hex of the session token. Unique so a lookup is a single index
    #: hit and a duplicate token can never exist.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    #: Double-submit CSRF token. Readable by the client (it is sent back in a
    #: header), so it is deliberately *not* the session token.
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)

    expires_at: Mapped[datetime] = timestamp_column(nullable=False)
    revoked_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    last_seen_at: Mapped[datetime] = timestamp_column(nullable=False, default=utc_now)

    #: Coarse client description for the owner's own review. Truncated by the
    #: use case; never used for an authorisation decision.
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_user_sessions_user_expires", "user_id", "expires_at"),
    )

    def is_usable(self, now: datetime) -> bool:
        """A session authenticates only while it is unrevoked and unexpired."""
        return self.revoked_at is None and self.expires_at > now

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        # The token hash is deliberately absent: this string ends up in logs.
        return f"<UserSession {self.id} user={self.user_id}>"
