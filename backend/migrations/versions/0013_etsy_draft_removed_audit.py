"""Phase 9 — Add etsy_draft_removed_externally to audit_action enum.

Revision ID: 0013_etsy_draft_removed_audit
Revises: 0012_phase_9_etsy_delivery
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_etsy_draft_removed_audit"
down_revision: str | None = "0012_phase_9_etsy_delivery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'etsy_draft_removed_externally';")


def downgrade() -> None:
    # PostgreSQL enum values cannot be dropped safely
    pass
