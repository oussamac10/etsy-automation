"""Phase 9 — Add etsy_verification fields to listing_drafts and audit_action enum.

Revision ID: 0015_phase_9_etsy_verification
Revises: 0014_phase_9_listing_fields
Create Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0015_phase_9_etsy_verification"
down_revision: str | None = "0014_phase_9_listing_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Extend audit_action enum
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'etsy_draft_verified';")

    # 2. Add verification columns to listing_drafts
    op.add_column(
        "listing_drafts",
        sa.Column("etsy_verification_status", sa.String(40), nullable=True),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("etsy_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("etsy_verification_result", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("listing_drafts", "etsy_verification_result")
    op.drop_column("listing_drafts", "etsy_verified_at")
    op.drop_column("listing_drafts", "etsy_verification_status")
