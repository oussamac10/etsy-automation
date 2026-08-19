"""Phase 9 — Remaining Etsy listing automation fields and owner listing defaults.

Revision ID: 0014_phase_9_listing_fields
Revises: 0013_etsy_draft_removed_audit
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0014_phase_9_listing_fields"
down_revision: str | None = "0013_etsy_draft_removed_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add fields to listing_drafts
    op.add_column(
        "listing_drafts",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="999"),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("sku", sa.String(60), nullable=True),
    )
    op.create_index("ix_listing_drafts_sku", "listing_drafts", ["sku"])

    op.add_column(
        "listing_drafts",
        sa.Column("shop_section_id", sa.String(60), nullable=True),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("shop_section_name", sa.String(120), nullable=True),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("should_auto_renew", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("etsy_properties", JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "listing_drafts",
        sa.Column(
            "primary_mockup_asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("shopping_cart_summary", sa.String(200), nullable=True),
    )

    op.create_check_constraint(
        "listing_quantity_positive",
        "listing_drafts",
        "quantity > 0",
    )

    # 2. Add listing defaults to owner_settings
    op.add_column(
        "owner_settings",
        sa.Column("default_digital_price_minor", sa.BigInteger(), nullable=False, server_default="499"),
    )
    op.add_column(
        "owner_settings",
        sa.Column("default_digital_quantity", sa.Integer(), nullable=False, server_default="999"),
    )
    op.add_column(
        "owner_settings",
        sa.Column("default_auto_renew", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "owner_settings",
        sa.Column("default_shop_section_strategy", sa.String(50), nullable=False, server_default="auto"),
    )

    op.create_check_constraint(
        "default_digital_price_positive",
        "owner_settings",
        "default_digital_price_minor > 0",
    )
    op.create_check_constraint(
        "default_digital_quantity_positive",
        "owner_settings",
        "default_digital_quantity > 0",
    )


def downgrade() -> None:
    op.drop_constraint("default_digital_quantity_positive", "owner_settings", type_="check")
    op.drop_constraint("default_digital_price_positive", "owner_settings", type_="check")
    op.drop_column("owner_settings", "default_shop_section_strategy")
    op.drop_column("owner_settings", "default_auto_renew")
    op.drop_column("owner_settings", "default_digital_quantity")
    op.drop_column("owner_settings", "default_digital_price_minor")

    op.drop_constraint("listing_quantity_positive", "listing_drafts", type_="check")
    op.drop_column("listing_drafts", "shopping_cart_summary")
    op.drop_column("listing_drafts", "primary_mockup_asset_id")
    op.drop_column("listing_drafts", "etsy_properties")
    op.drop_column("listing_drafts", "should_auto_renew")
    op.drop_column("listing_drafts", "shop_section_name")
    op.drop_column("listing_drafts", "shop_section_id")
    op.drop_index("ix_listing_drafts_sku", table_name="listing_drafts")
    op.drop_column("listing_drafts", "sku")
    op.drop_column("listing_drafts", "quantity")
