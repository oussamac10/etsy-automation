"""Etsy shop connection model with encrypted OAuth tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin, timestamp_column

if TYPE_CHECKING:
    from app.infrastructure.models.user import User


class ShopConnection(UuidMixin, TimestampMixin, Base):
    """The mapping of an application owner to their connected Etsy shop.

    Holds OAuth 2.0 access and refresh tokens encrypted with Fernet + HKDF at rest.
    Plaintext tokens are never stored in any column.
    """

    __tablename__ = "shop_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="etsy")

    etsy_user_id: Mapped[str] = mapped_column(String(60), nullable=False)
    etsy_shop_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    etsy_shop_name: Mapped[str] = mapped_column(String(120), nullable=False)

    #: Fernet ciphertext tokens. Binary rather than text so nothing reads them as display values.
    ciphertext_access_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ciphertext_refresh_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    #: Which ENCRYPTION_KEY_VERSION produced the ciphertexts.
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)

    token_expires_at: Mapped[datetime] = timestamp_column(nullable=False)
    granted_scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), nullable=False, default=list
    )

    #: Status: 'connected', 'refresh_required', 'reauthorization_required', 'disconnected'
    connection_status: Mapped[str] = mapped_column(String(40), nullable=False, default="connected")
    last_refreshed_at: Mapped[datetime | None] = timestamp_column(nullable=True)

    user: Mapped[User] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_shop_connection_user_provider"),
        CheckConstraint("key_version >= 1", name="shop_connection_key_version_positive"),
        CheckConstraint("octet_length(ciphertext_access_token) > 0", name="access_token_not_empty"),
        CheckConstraint(
            "octet_length(ciphertext_refresh_token) > 0", name="refresh_token_not_empty"
        ),
    )

    @property
    def shop_id(self) -> str:
        """Alias for etsy_shop_id."""
        return self.etsy_shop_id

    @property
    def is_connected(self) -> bool:
        """True if the shop connection is actively connected and not disconnected/revoked."""
        return self.connection_status in {"connected", "refresh_required"}

    @property
    def is_token_expired(self) -> bool:
        """True if the access token has passed its expiration timestamp."""
        return datetime.now(UTC) >= self.token_expires_at
