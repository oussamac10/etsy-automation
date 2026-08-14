"""Phase 6 — Gemini provider.

Adds value 'gemini' to 'provider_name' enum.

Revision ID: 0006_phase_6_gemini
Revises: 0005_phase_5_research_outbox
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_phase_6_gemini"
down_revision: str | None = "0005_phase_5_research_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add value 'gemini' to 'provider_name' enum
    op.execute("ALTER TYPE provider_name ADD VALUE IF NOT EXISTS 'gemini'")


def downgrade() -> None:
    # Adding enum values cannot be easily reversed in a transaction in Postgres,
    # so we keep it as a no-op.
    pass
