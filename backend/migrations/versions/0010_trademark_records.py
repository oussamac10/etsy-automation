"""Phase 8 — PostgreSQL USPTO Trademark Records table and indexes.

Revision ID: 0010_trademark_records
Revises: 0009_phase_7_mockups
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0010_trademark_records"
down_revision: str | None = "0009_phase_7_mockups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable PostgreSQL trigram extension for indexed fuzzy similarity matching
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Drop table if previously created under earlier draft schema
    op.execute("DROP TABLE IF EXISTS trademark_records CASCADE;")

    op.create_table(
        "trademark_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mark_text", sa.String(512), nullable=False),
        sa.Column("normalized_mark_text", sa.String(512), nullable=False),
        sa.Column("serial_number", sa.String(64), nullable=True),
        sa.Column("registration_number", sa.String(64), nullable=True),
        sa.Column("status_code", sa.String(32), nullable=True),
        sa.Column("status_text", sa.String(64), nullable=False, server_default="REGISTERED"),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("classes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("goods_services", sa.Text(), nullable=True),
        sa.Column("owner_name", sa.String(512), nullable=True),
        sa.Column("filing_date", sa.String(32), nullable=True),
        sa.Column("registration_date", sa.String(32), nullable=True),
        sa.Column("source_file", sa.String(512), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_trademark_records_serial_number",
        "trademark_records",
        ["serial_number"],
        unique=True,
        postgresql_where=sa.text("serial_number IS NOT NULL"),
    )
    op.create_index("ix_trademark_records_normalized_mark_text", "trademark_records", ["normalized_mark_text"])
    op.create_index("ix_trademark_records_mark_text", "trademark_records", ["mark_text"])
    op.create_index("ix_trademark_records_registration_number", "trademark_records", ["registration_number"])
    op.create_index("ix_trademark_records_is_live", "trademark_records", ["is_live"])
    op.create_index("ix_trademark_records_norm_live", "trademark_records", ["normalized_mark_text", "is_live"])

    # High-performance GIN trigram index for phrase similarity and substring lookups
    op.create_index(
        "ix_trademark_records_trgm",
        "trademark_records",
        ["normalized_mark_text"],
        postgresql_using="gin",
        postgresql_ops={"normalized_mark_text": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_table("trademark_records")

