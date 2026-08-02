"""The owner's settings and their encrypted provider credentials.

Two tables, one owner-scoped each:

* ``owner_settings`` — one row per user, created on first read. Defaults live in
  ``app/domain/owner_settings.py`` so the API, the column defaults and the tests
  agree on one list.
* ``provider_credentials`` — one row per (user, provider). The plaintext never
  exists in a column; only the Fernet ciphertext, the key version that produced
  it, and a masked suffix safe to display.

Budgets are ``BIGINT`` minor units like the rest of the ledger, never a float.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import IdeaMode, ProviderName, QualityTier
from app.domain.money import Money
from app.domain.owner_settings import (
    DEFAULT_CURRENCY,
    DEFAULT_LANGUAGE,
    DEFAULT_MARKETPLACE,
    DEFAULT_TARGET_COUNTRY,
    MAX_STYLE_PREFERENCES,
)
from app.infrastructure.models.base import (
    Base,
    TimestampMixin,
    UuidMixin,
    pg_enum,
)

if TYPE_CHECKING:
    from app.infrastructure.models.user import User

#: Defaults expressed in minor units so the column default matches the domain
#: constant without a runtime conversion.
DEFAULT_DAILY_BUDGET_MINOR = 200
DEFAULT_MONTHLY_BUDGET_MINOR = 3000


class OwnerSettings(UuidMixin, TimestampMixin, Base):
    """One settings row per owner.

    ``user_id`` is unique rather than the primary key so the table follows the
    same UUID-PK convention as everything else, while the database still refuses
    a second settings row for the same person.
    """

    __tablename__ = "owner_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # --- Target market -----------------------------------------------------
    target_marketplace: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DEFAULT_MARKETPLACE
    )
    target_country: Mapped[str] = mapped_column(
        String(2), nullable=False, default=DEFAULT_TARGET_COUNTRY
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default=DEFAULT_CURRENCY)
    default_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default=DEFAULT_LANGUAGE
    )

    # --- Idea and research preferences -------------------------------------
    default_idea_mode: Mapped[IdeaMode] = mapped_column(
        pg_enum(IdeaMode, "idea_mode"), nullable=False, default=IdeaMode.MARKET_LED
    )
    default_target_buyer: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Physical products a design is normally intended for. Enum *values*.
    default_product_uses: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, default=list
    )

    # --- Style -------------------------------------------------------------
    #: Free text on purpose: a style vocabulary the owner cannot extend would be
    #: useless. Bounded in length and count instead.
    style_preferences: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), nullable=False, default=list
    )
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Subjects, motifs or phrases never to generate. Also enforced downstream;
    #: this is the owner's standing instruction, not the only safeguard.
    avoid_terms: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False, default=list)

    # --- Quality -----------------------------------------------------------
    default_quality_tier: Mapped[QualityTier] = mapped_column(
        pg_enum(QualityTier, "quality_tier"), nullable=False, default=QualityTier.DRAFT
    )
    min_output_pixels: Mapped[int] = mapped_column(Integer, nullable=False, default=3000)
    require_transparent_background: Mapped[bool] = mapped_column(nullable=False, default=True)

    # --- Budgets (minor units of ``currency``) ------------------------------
    daily_budget_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=DEFAULT_DAILY_BUDGET_MINOR
    )
    monthly_budget_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=DEFAULT_MONTHLY_BUDGET_MINOR
    )

    # --- Schedule and notifications ----------------------------------------
    weekly_research_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    #: 0 = Monday, matching ``datetime.weekday()``.
    weekly_research_weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weekly_research_hour_utc: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    notify_on_failure: Mapped[bool] = mapped_column(nullable=False, default=True)
    notify_on_budget_warning: Mapped[bool] = mapped_column(nullable=False, default=True)
    notify_on_approval_needed: Mapped[bool] = mapped_column(nullable=False, default=True)

    user: Mapped[User] = relationship(back_populates="settings")

    __table_args__ = (
        # Invariants the API also checks. They live here too because a bug in a
        # future use case must not be able to write an impossible settings row.
        CheckConstraint("daily_budget_minor >= 0", name="daily_budget_non_negative"),
        CheckConstraint("monthly_budget_minor >= 0", name="monthly_budget_non_negative"),
        CheckConstraint("daily_budget_minor <= monthly_budget_minor", name="daily_within_monthly"),
        CheckConstraint("char_length(target_country) = 2", name="target_country_alpha2"),
        CheckConstraint("char_length(currency) = 3", name="currency_alpha3"),
        CheckConstraint("min_output_pixels BETWEEN 512 AND 20000", name="output_pixels_range"),
        CheckConstraint(
            "weekly_research_weekday BETWEEN 0 AND 6", name="weekly_research_weekday_range"
        ),
        CheckConstraint(
            "weekly_research_hour_utc BETWEEN 0 AND 23", name="weekly_research_hour_range"
        ),
        CheckConstraint(
            f"cardinality(style_preferences) <= {MAX_STYLE_PREFERENCES}",
            name="style_preferences_bounded",
        ),
    )

    @property
    def daily_budget(self) -> Money:
        return Money(self.daily_budget_minor, self.currency)

    @property
    def monthly_budget(self) -> Money:
        return Money(self.monthly_budget_minor, self.currency)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<OwnerSettings user={self.user_id} {self.target_country}/{self.currency}>"


class ProviderCredential(UuidMixin, TimestampMixin, Base):
    """One encrypted secret for one provider, owned by one user.

    There is no column that can hold plaintext. ``masked_value`` is derived at
    write time from the plaintext and is the only representation the API returns.
    """

    __tablename__ = "provider_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ProviderName] = mapped_column(
        pg_enum(ProviderName, "provider_name"), nullable=False
    )

    #: Fernet token. Binary rather than text so nothing is tempted to read it as
    #: a display value.
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    #: Which ``ENCRYPTION_KEY_VERSION`` produced ``ciphertext``. A mismatch is
    #: reported as a configuration error rather than a decryption failure.
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)

    #: Bullets plus the last few characters. Safe to render.
    masked_value: Mapped[str] = mapped_column(String(40), nullable=False)
    #: The owner's own note, e.g. which account the key belongs to.
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship(back_populates="provider_credentials")

    __table_args__ = (
        # One credential per provider per owner: replacing a key is an update,
        # so a stale secret cannot linger beside its replacement.
        UniqueConstraint("user_id", "provider", name="uq_provider_credentials_user_provider"),
        CheckConstraint("key_version >= 1", name="key_version_positive"),
        CheckConstraint("octet_length(ciphertext) > 0", name="ciphertext_not_empty"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ProviderCredential {self.provider} user={self.user_id}>"
