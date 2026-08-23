"""Add is_muted column to telegram_connections.

Revision ID: 0017_telegram_mute
Revises: 0016_listing_provenance
Create Date: 2026-08-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_telegram_mute"
down_revision: str | None = "0016_listing_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "telegram_connections",
        sa.Column("is_muted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("telegram_connections", "is_muted")
