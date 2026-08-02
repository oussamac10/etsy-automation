"""Phase 4 — Telegram Remote Control.

Adds the `telegram_connections` table to store verified Telegram accounts
and short-lived pairing codes. Adds `is_paused` flag to `owner_settings`.
Appends `telegram_paired` and `telegram_disconnected` to `audit_action`.

Revision ID: 0004_phase_4_telegram
Revises: 0003_phase_3_auth_settings
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase_4_telegram"
down_revision: str | None = "0003_phase_3_auth_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_AUDIT_ACTIONS = (
    "telegram_paired",
    "telegram_disconnected",
)


def upgrade() -> None:
    # 1. Update audit_action enum values
    for value in NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'")

    # 2. Add is_paused to owner_settings
    op.add_column(
        "owner_settings",
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 3. Create telegram_connections table
    op.create_table(
        "telegram_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=120), nullable=True),
        sa.Column("pairing_code_hash", sa.String(length=64), nullable=True),
        sa.Column("pairing_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_pairing_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            "failed_pairing_attempts >= 0",
            name=op.f("ck_telegram_connections_non_negative_failed_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_telegram_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_connections")),
        sa.UniqueConstraint("user_id", name=op.f("uq_telegram_connections_user_id")),
        sa.UniqueConstraint(
            "telegram_user_id", name=op.f("uq_telegram_connections_telegram_user_id")
        ),
    )
    op.create_index(
        op.f("ix_telegram_connections_pairing_code_hash"),
        "telegram_connections",
        ["pairing_code_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_telegram_connections_pairing_code_hash"),
        table_name="telegram_connections",
    )
    op.drop_table("telegram_connections")
    op.drop_column("owner_settings", "is_paused")
