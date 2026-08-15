"""Phase 7 — Printful realistic mockup generator and mockup jobs table.

Revision ID: 0009_phase_7_printful_mockups
Revises: 0008_phase_6_telegram
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_phase_7_printful_mockups"
down_revision: str | None = "0008_phase_6_telegram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add 'printful' to provider_name enum
    op.execute("ALTER TYPE provider_name ADD VALUE IF NOT EXISTS 'printful'")

    # 2. Create mockup_jobs table
    op.create_table(
        "mockup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_workflows.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "production_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "master_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "output_asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM(name="provider_name", create_type=False),
            nullable=False,
        ),
        sa.Column("external_task_id", sa.String(length=200), nullable=True),
        sa.Column("product_type", sa.String(length=60), nullable=False),
        sa.Column("provider_product_id", sa.Integer(), nullable=True),
        sa.Column("variant_ids", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
        sa.Column("placement", sa.String(length=60), nullable=False, server_default="front"),
        sa.Column(
            "status",
            postgresql.ENUM(name="job_status", create_type=False),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_mockup_url", sa.Text(), nullable=True),
        sa.Column("failure_kind", sa.String(length=60), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("production_job_id", "product_type", name="uq_mockup_job_production_product"),
        sa.CheckConstraint("attempt_count >= 0", name="mockup_attempt_non_negative"),
    )
    op.create_index(
        "ix_mockup_jobs_workflow_status",
        "mockup_jobs",
        ["workflow_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_mockup_jobs_workflow_status", table_name="mockup_jobs")
    op.drop_table("mockup_jobs")
