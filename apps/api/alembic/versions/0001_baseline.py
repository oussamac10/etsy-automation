"""Baseline revision.

Phase 1 creates no application tables — the domain entities land in Phase 2.
This revision exists so the migration chain, the ``alembic_version`` table and
the CI migration check are proven against a fresh database before any schema
depends on them.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
