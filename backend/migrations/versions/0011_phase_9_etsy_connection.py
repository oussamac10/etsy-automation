"""Phase 9 — Etsy ShopConnection and ListingDraft Etsy metadata.

Revision ID: 0011_phase_9_etsy_connection
Revises: 0010_trademark_records
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision: str = "0011_phase_9_etsy_connection"
down_revision: str | None = "0010_trademark_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new audit_action enum values if missing
    for action in (
        "etsy_connected",
        "etsy_disconnected",
        "etsy_token_refreshed",
        "etsy_draft_created",
        "etsy_draft_failed",
    ):
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}';")

    # 2. Create shop_connections table
    op.create_table(
        "shop_connections",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(30), nullable=False, server_default="etsy"),
        sa.Column("etsy_user_id", sa.String(60), nullable=False),
        sa.Column("etsy_shop_id", sa.String(60), nullable=False),
        sa.Column("etsy_shop_name", sa.String(120), nullable=False),
        sa.Column("ciphertext_access_token", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext_refresh_token", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "granted_scopes",
            ARRAY(sa.String(60)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "connection_status",
            sa.String(40),
            nullable=False,
            server_default="connected",
        ),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_shop_connection_user_provider"),
        sa.CheckConstraint("key_version >= 1", name="shop_connection_key_version_positive"),
        sa.CheckConstraint(
            "octet_length(ciphertext_access_token) > 0", name="access_token_not_empty"
        ),
        sa.CheckConstraint(
            "octet_length(ciphertext_refresh_token) > 0", name="refresh_token_not_empty"
        ),
    )
    op.create_index("ix_shop_connections_user_id", "shop_connections", ["user_id"])
    op.create_index("ix_shop_connections_etsy_shop_id", "shop_connections", ["etsy_shop_id"])

    # 3. Add Etsy fields to listing_drafts
    op.add_column("listing_drafts", sa.Column("etsy_shop_id", sa.String(60), nullable=True))
    op.add_column("listing_drafts", sa.Column("etsy_listing_url", sa.String(500), nullable=True))
    op.add_column(
        "listing_drafts",
        sa.Column("etsy_state", sa.String(30), nullable=True, server_default="draft"),
    )
    op.add_column(
        "listing_drafts",
        sa.Column(
            "etsy_image_ids",
            ARRAY(sa.String(60)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    op.add_column("listing_drafts", sa.Column("etsy_file_id", sa.String(60), nullable=True))
    op.add_column(
        "listing_drafts",
        sa.Column(
            "etsy_dispatch_status",
            sa.String(40),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "listing_drafts",
        sa.Column("etsy_last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("listing_drafts", sa.Column("etsy_failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    # 1. Drop added columns from listing_drafts
    op.drop_column("listing_drafts", "etsy_failure_reason")
    op.drop_column("listing_drafts", "etsy_last_synced_at")
    op.drop_column("listing_drafts", "etsy_dispatch_status")
    op.drop_column("listing_drafts", "etsy_file_id")
    op.drop_column("listing_drafts", "etsy_image_ids")
    op.drop_column("listing_drafts", "etsy_state")
    op.drop_column("listing_drafts", "etsy_listing_url")
    op.drop_column("listing_drafts", "etsy_shop_id")

    # 2. Drop shop_connections table
    op.drop_table("shop_connections")
