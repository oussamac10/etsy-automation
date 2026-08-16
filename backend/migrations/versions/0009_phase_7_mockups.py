"""Phase 7 — Print-Ready Master PNG production and generic mockup pipeline.

Revision ID: 0009_phase_7_mockups
Revises: 0008_phase_6_telegram
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence
from alembic import op

revision: str = "0009_phase_7_mockups"
down_revision: str | None = "0008_phase_6_telegram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase 7 uses S3 object storage for user-uploaded mockup templates
    # and records composited mockups as standard Asset rows.
    # Safely clean up any leftover mockup_jobs table if it existed.
    op.execute("DROP TABLE IF EXISTS mockup_jobs CASCADE")


def downgrade() -> None:
    pass
