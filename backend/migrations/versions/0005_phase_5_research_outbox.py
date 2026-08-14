"""Phase 5 — Research and outbox.

Creates the `outbox_messages` table to support transactional dispatch of worker jobs.

Revision ID: 0005_phase_5_research_outbox
Revises: 0004_phase_4_telegram
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase_5_research_outbox"
down_revision: str | None = "0004_phase_4_telegram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add value 'tavily' to 'provider_name' enum
    op.execute("ALTER TYPE provider_name ADD VALUE IF NOT EXISTS 'tavily'")

    # Add idempotency_key column to research_runs
    op.add_column(
        "research_runs",
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
    )
    op.create_unique_constraint(
        "uq_research_runs_idempotency_key",
        "research_runs",
        ["idempotency_key"],
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_messages")),
    )
    op.create_index(
        op.f("ix_outbox_messages_processed"),
        "outbox_messages",
        ["processed"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_outbox_messages_processed"),
        table_name="outbox_messages",
    )
    op.drop_table("outbox_messages")

    op.execute(
        "ALTER TABLE research_runs "
        "DROP CONSTRAINT IF EXISTS uq_research_runs_idempotency_key"
    )
    op.execute("ALTER TABLE research_runs DROP COLUMN IF EXISTS idempotency_key")
