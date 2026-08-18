"""add_idempotency_key

Revision ID: 0007_add_idempotency_key
Revises: 0006_phase_6_gemini
Create Date: 2026-08-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_idempotency_key"
down_revision: str | None = "0006_phase_6_gemini"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Add idempotency_key to research_runs if not present
    columns = [col["name"] for col in inspector.get_columns("research_runs")]
    if "idempotency_key" not in columns:
        op.add_column(
            "research_runs", sa.Column("idempotency_key", sa.String(length=200), nullable=True)
        )
        op.create_unique_constraint(
            op.f("uq_research_runs_idempotency_key"), "research_runs", ["idempotency_key"]
        )

    # 2. Align telegram_connections unique constraints to indices to match model
    constraints = inspector.get_unique_constraints("telegram_connections")
    constraint_names = {c["name"] for c in constraints}

    if "uq_telegram_connections_telegram_user_id" in constraint_names:
        op.drop_constraint(
            "uq_telegram_connections_telegram_user_id", "telegram_connections", type_="unique"
        )
    if "uq_telegram_connections_user_id" in constraint_names:
        op.drop_constraint(
            "uq_telegram_connections_user_id", "telegram_connections", type_="unique"
        )

    indexes = inspector.get_indexes("telegram_connections")
    index_names = {idx["name"] for idx in indexes}

    if "ix_telegram_connections_telegram_user_id" not in index_names:
        op.create_index(
            "ix_telegram_connections_telegram_user_id",
            "telegram_connections",
            ["telegram_user_id"],
            unique=True,
        )
    if "ix_telegram_connections_user_id" not in index_names:
        op.create_index(
            "ix_telegram_connections_user_id", "telegram_connections", ["user_id"], unique=True
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Revert telegram_connections indices back to constraints
    indexes = inspector.get_indexes("telegram_connections")
    index_names = {idx["name"] for idx in indexes}

    if "ix_telegram_connections_user_id" in index_names:
        op.drop_index("ix_telegram_connections_user_id", table_name="telegram_connections")
    if "ix_telegram_connections_telegram_user_id" in index_names:
        op.drop_index("ix_telegram_connections_telegram_user_id", table_name="telegram_connections")

    constraints = inspector.get_unique_constraints("telegram_connections")
    constraint_names = {c["name"] for c in constraints}

    if "uq_telegram_connections_user_id" not in constraint_names:
        op.create_unique_constraint(
            "uq_telegram_connections_user_id", "telegram_connections", ["user_id"]
        )
    if "uq_telegram_connections_telegram_user_id" not in constraint_names:
        op.create_unique_constraint(
            "uq_telegram_connections_telegram_user_id", "telegram_connections", ["telegram_user_id"]
        )

    # 2. Revert research_runs idempotency_key if present
    columns = [col["name"] for col in inspector.get_columns("research_runs")]
    if "idempotency_key" in columns:
        op.drop_constraint(
            op.f("uq_research_runs_idempotency_key"), "research_runs", type_="unique"
        )
        op.drop_column("research_runs", "idempotency_key")
