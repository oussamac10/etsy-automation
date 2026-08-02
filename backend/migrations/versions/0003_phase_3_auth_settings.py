"""Phase 3 — authentication and settings.

Adds the password hash to ``users``, the server-side session table, the owner's
settings row and the encrypted provider-credential store.

Two notes on the enum types:

* ``quality_tier`` is new and is created and dropped by this revision.
* ``audit_action`` gains six security-relevant values. PostgreSQL cannot remove
  an enum value, so the downgrade leaves them in place; ``ADD VALUE IF NOT
  EXISTS`` keeps a downgrade-then-upgrade cycle repeatable.

Revision ID: 0003_phase_3_auth_settings
Revises: 0002_phase_2_domain
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase_3_auth_settings"
down_revision: str | None = "0002_phase_2_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUALITY_TIER_VALUES = ("draft", "standard", "final")

#: Appended to ``audit_action`` by this revision.
NEW_AUDIT_ACTIONS = (
    "login_succeeded",
    "login_failed",
    "logout",
    "settings_updated",
    "credential_stored",
    "credential_deleted",
)

PROVIDER_NAME_VALUES = ("fake", "openai", "recraft", "etsy", "uspto")
IDEA_MODE_VALUES = ("market-led", "user-idea", "hybrid")


def upgrade() -> None:
    postgresql.ENUM(*QUALITY_TIER_VALUES, name="quality_tier").create(
        op.get_bind(), checkfirst=True
    )
    for value in NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")

    # Nullable: an owner row can exist before a password is set (fixtures, and
    # the bootstrap command). ``User.can_authenticate`` treats NULL as "cannot".
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_user_sessions_expiry_after_creation")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_user_expires", "user_sessions", ["user_id", "expires_at"])

    op.create_table(
        "owner_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_marketplace", sa.String(length=50), nullable=False),
        sa.Column("target_country", sa.String(length=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("default_language", sa.String(length=10), nullable=False),
        sa.Column(
            "default_idea_mode",
            postgresql.ENUM(*IDEA_MODE_VALUES, name="idea_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("default_target_buyer", sa.Text(), nullable=True),
        sa.Column("default_product_uses", sa.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("style_preferences", sa.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("style_notes", sa.Text(), nullable=True),
        sa.Column("avoid_terms", sa.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column(
            "default_quality_tier",
            postgresql.ENUM(*QUALITY_TIER_VALUES, name="quality_tier", create_type=False),
            nullable=False,
        ),
        sa.Column("min_output_pixels", sa.Integer(), nullable=False),
        sa.Column("require_transparent_background", sa.Boolean(), nullable=False),
        sa.Column("daily_budget_minor", sa.BigInteger(), nullable=False),
        sa.Column("monthly_budget_minor", sa.BigInteger(), nullable=False),
        sa.Column("weekly_research_enabled", sa.Boolean(), nullable=False),
        sa.Column("weekly_research_weekday", sa.Integer(), nullable=False),
        sa.Column("weekly_research_hour_utc", sa.Integer(), nullable=False),
        sa.Column("notify_on_failure", sa.Boolean(), nullable=False),
        sa.Column("notify_on_budget_warning", sa.Boolean(), nullable=False),
        sa.Column("notify_on_approval_needed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # The same invariants the API validates. A future use case with a bug
        # still cannot write an impossible settings row.
        sa.CheckConstraint(
            "daily_budget_minor >= 0", name=op.f("ck_owner_settings_daily_budget_non_negative")
        ),
        sa.CheckConstraint(
            "monthly_budget_minor >= 0",
            name=op.f("ck_owner_settings_monthly_budget_non_negative"),
        ),
        sa.CheckConstraint(
            "daily_budget_minor <= monthly_budget_minor",
            name=op.f("ck_owner_settings_daily_within_monthly"),
        ),
        sa.CheckConstraint(
            "char_length(target_country) = 2",
            name=op.f("ck_owner_settings_target_country_alpha2"),
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3", name=op.f("ck_owner_settings_currency_alpha3")
        ),
        sa.CheckConstraint(
            "min_output_pixels BETWEEN 512 AND 20000",
            name=op.f("ck_owner_settings_output_pixels_range"),
        ),
        sa.CheckConstraint(
            "weekly_research_weekday BETWEEN 0 AND 6",
            name=op.f("ck_owner_settings_weekly_research_weekday_range"),
        ),
        sa.CheckConstraint(
            "weekly_research_hour_utc BETWEEN 0 AND 23",
            name=op.f("ck_owner_settings_weekly_research_hour_range"),
        ),
        sa.CheckConstraint(
            "cardinality(style_preferences) <= 20",
            name=op.f("ck_owner_settings_style_preferences_bounded"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_owner_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_owner_settings")),
        sa.UniqueConstraint("user_id", name=op.f("uq_owner_settings_user_id")),
    )

    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM(*PROVIDER_NAME_VALUES, name="provider_name", create_type=False),
            nullable=False,
        ),
        # No plaintext column exists, by design.
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("masked_value", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "key_version >= 1", name=op.f("ck_provider_credentials_key_version_positive")
        ),
        sa.CheckConstraint(
            "octet_length(ciphertext) > 0",
            name=op.f("ck_provider_credentials_ciphertext_not_empty"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_provider_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_credentials")),
        sa.UniqueConstraint("user_id", "provider", name="uq_provider_credentials_user_provider"),
    )
    op.create_index(op.f("ix_provider_credentials_user_id"), "provider_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_provider_credentials_user_id"), table_name="provider_credentials")
    op.drop_table("provider_credentials")
    op.drop_table("owner_settings")
    op.drop_index("ix_user_sessions_user_expires", table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_column("users", "password_hash")
    postgresql.ENUM(*QUALITY_TIER_VALUES, name="quality_tier").drop(op.get_bind(), checkfirst=True)
    # ``audit_action`` keeps the appended values: PostgreSQL has no DROP VALUE,
    # and recreating the type would rewrite the append-only audit table.
