"""Phase 9 — Etsy Multi-File Delivery & Taxonomy Path.

Revision ID: 0012_phase_9_etsy_delivery
Revises: 0011_phase_9_etsy_connection
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0012_phase_9_etsy_delivery"
down_revision: str | None = "0011_phase_9_etsy_connection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add taxonomy_path to listing_drafts
    op.add_column(
        "listing_drafts",
        sa.Column("taxonomy_path", sa.String(500), nullable=True),
    )

    # 2. Add etsy_file_ids to listing_drafts
    op.add_column(
        "listing_drafts",
        sa.Column(
            "etsy_file_ids",
            ARRAY(sa.String(60)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )

    # 3. Backfill etsy_file_ids from existing etsy_file_id if present
    op.execute(
        """
        UPDATE listing_drafts
        SET etsy_file_ids = ARRAY[etsy_file_id]
        WHERE etsy_file_id IS NOT NULL AND cardinality(etsy_file_ids) = 0;
        """
    )


def downgrade() -> None:
    op.drop_column("listing_drafts", "etsy_file_ids")
    op.drop_column("listing_drafts", "taxonomy_path")
