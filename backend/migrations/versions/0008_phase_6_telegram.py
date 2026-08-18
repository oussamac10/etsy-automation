"""Phase 6 — Telegram provider.

Adds value 'telegram' to 'provider_name' enum.

Revision ID: 0008_phase_6_telegram
Revises: 0007_add_idempotency_key
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_phase_6_telegram"
down_revision: str | None = "0007_add_idempotency_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add value 'telegram' to 'provider_name' enum
    op.execute("ALTER TYPE provider_name ADD VALUE IF NOT EXISTS 'telegram'")


def downgrade() -> None:
    pass
