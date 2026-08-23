from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin, timestamp_column

if TYPE_CHECKING:
    from app.infrastructure.models.user import User


class TelegramConnection(UuidMixin, TimestampMixin, Base):
    """The mapping of an application owner to their Telegram chat/user profile.

    Supports secure account pairing using short-lived cryptographically secure codes.
    """

    __tablename__ = "telegram_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(120), nullable=True)

    #: Whether notifications to this Telegram chat are currently muted.
    is_muted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    #: SHA-256 hex hash of the pairing code.
    pairing_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pairing_code_expires_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    failed_pairing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    paired_at: Mapped[datetime | None] = timestamp_column(nullable=True)
    revoked_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    user: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint("failed_pairing_attempts >= 0", name="non_negative_failed_attempts"),
    )

    @property
    def is_paired(self) -> bool:
        """True if the connection has been successfully paired and not revoked."""
        return self.telegram_user_id is not None and self.revoked_at is None
