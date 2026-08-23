"""Add provenance and context hash columns to listing_drafts.

Revision ID: 0016_listing_provenance
Revises: 0015_phase_9_etsy_verification
Create Date: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0016_listing_provenance"
down_revision: str | None = "0015_phase_9_etsy_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "listing_drafts",
        sa.Column(
            "concept_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_concepts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("concept_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "listing_drafts",
        sa.Column(
            "artwork_asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("listing_context_hash", sa.String(64), nullable=True),
    )

    op.create_index("ix_listing_drafts_concept_id", "listing_drafts", ["concept_id"])
    op.create_index(
        "ix_listing_drafts_listing_context_hash",
        "listing_drafts",
        ["listing_context_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_listing_drafts_listing_context_hash", table_name="listing_drafts")
    op.drop_index("ix_listing_drafts_concept_id", table_name="listing_drafts")
    op.drop_column("listing_drafts", "listing_context_hash")
    op.drop_column("listing_drafts", "artwork_asset_id")
    op.drop_column("listing_drafts", "concept_version")
    op.drop_column("listing_drafts", "concept_id")
