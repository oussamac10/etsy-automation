#!/usr/bin/env python3
"""Automated Database Schema Documentation Generator.

Extracts all table metadata, columns, constraints, foreign keys, and indexes directly
from SQLAlchemy ``Base.metadata`` and renders a complete, up-to-date Markdown
documentation file at ``docs/DATABASE_SCHEMA.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import CheckConstraint, Table, UniqueConstraint  # noqa: E402

import app.infrastructure.models  # noqa: F401, E402
from app.infrastructure.database import Base  # noqa: E402

DOCS_PATH = REPO_ROOT / "docs" / "DATABASE_SCHEMA.md"

DOMAINS: dict[str, list[str]] = {
    "Authentication & Settings": [
        "users",
        "user_sessions",
        "owner_settings",
        "provider_credentials",
        "telegram_connections",
        "shop_connections",
    ],
    "Workflow & State Machine Core": [
        "product_workflows",
        "workflow_transitions",
        "workflow_failures",
        "approvals",
        "audit_events",
        "outbox_messages",
    ],
    "Phase 1 & Phase 2: Idea & Market Research": [
        "original_ideas",
        "original_idea_revisions",
        "research_runs",
        "research_evidence",
        "keyword_clusters",
    ],
    "Phase 3 & Phase 4: Concepts & Artwork": [
        "product_concepts",
        "design_prompts",
        "artwork_jobs",
        "provider_usage",
    ],
    "Phase 7 & Phase 8: Production, Mockups, IP & Publishing": [
        "assets",
        "production_jobs",
        "listing_drafts",
        "trademark_records",
    ],
}

TABLE_DESCRIPTIONS: dict[str, str] = {
    "users": "System user accounts, credentials, and authentication records.",
    "user_sessions": (
        "Active web session tokens, CSRF protection hashes, and expiration timestamps."
    ),
    "owner_settings": (
        "Tenant/owner preferences, default marketplace options, and mockup presets."
    ),
    "provider_credentials": ("Encrypted third-party API keys (Recraft, Gemini, Tavily, OpenAI)."),
    "telegram_connections": (
        "Paired Telegram accounts for 2-way approval gate workflows and notifications."
    ),
    "product_workflows": ("Central aggregate managing the lifecycle of an automated product line."),
    "workflow_transitions": (
        "Immutable audit log of all state machine transitions with optimistic locking."
    ),
    "workflow_failures": (
        "Structured error logs, triage categories, and exponential retry schedules."
    ),
    "approvals": ("Gate decisions (Approved/Rejected/Refined) made via Web UI or Telegram."),
    "audit_events": ("Comprehensive system audit event stream tracking mutations and decisions."),
    "outbox_messages": (
        "Transactional Outbox table for atomic event publishing to workers/external systems."
    ),
    "original_ideas": "Initial seed ideas or user prompt inputs initiating a workflow.",
    "original_idea_revisions": "Versioned revisions of original ideas and prompt tweaks.",
    "research_runs": "Market research execution tracking with evidence synthesis and queries.",
    "research_evidence": (
        "Individual trend, buyer intent, and seasonality signals gathered from web search."
    ),
    "keyword_clusters": (
        "Extracted SEO keyword groupings, search volume signals, and buyer intent tiers."
    ),
    "product_concepts": (
        "Materially differentiated product design concepts scored across multiple metrics."
    ),
    "design_prompts": (
        "Engineered positive/negative prompts, typography directives, and style notes."
    ),
    "artwork_jobs": "Image generation and refinement jobs executed across AI providers.",
    "provider_usage": "Granular token usage, compute duration, and API cost accounting per job.",
    "assets": "Canonical object storage registry for artwork, master print PNGs, and mockups.",
    "production_jobs": (
        "Print-ready 4500x5400 @ 300 DPI master PNG processing & QA check pipeline."
    ),
    "listing_drafts": "Finalized Etsy product listing copy, tags, pricing, and draft assets.",
    "shop_connections": (
        "Etsy OAuth 2.0 shop connections, encrypted tokens at rest, scopes, and connection status."
    ),
    "trademark_records": (
        "PostgreSQL USPTO Trademark Registry mirror with trigram fuzzy search and TSDR status."
    ),
}


def _format_type(col: Any) -> str:
    type_str = str(col.type)
    return type_str


def _format_default(col: Any) -> str:
    if col.default is not None:
        arg = getattr(col.default, "arg", None)
        if callable(arg):
            return "dynamic"
        return str(arg) if arg is not None else "-"
    if col.server_default is not None:
        arg = getattr(col.server_default, "arg", None)
        return str(arg) if arg is not None else "-"
    return "-"


def generate_mermaid_erd(tables: dict[str, Table]) -> str:
    lines = ["```mermaid", "erDiagram"]
    for table_name, table in sorted(tables.items()):
        sorted_fks = sorted(
            table.foreign_keys,
            key=lambda fk: (fk.column.table.name, fk.parent.name, fk.column.name),
        )
        for fk in sorted_fks:
            target_table = fk.column.table.name
            fk_col = fk.parent.name
            target_col = fk.column.name
            lines.append(f'    {target_table} ||--o{{ {table_name} : "{fk_col} -> {target_col}"')
    lines.append("```")
    return "\n".join(lines)


def generate_schema_markdown() -> str:
    tables = Base.metadata.tables

    lines: list[str] = []
    lines.append("# PostgreSQL Database Schema Documentation")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append(
        "> This document is automatically generated from SQLAlchemy model definitions in "
        "`backend/app/infrastructure/models/`. "
        "Run `python backend/scripts/generate_schema_docs.py` "
        "to update this document whenever models change."
    )
    lines.append("")
    lines.append("## Overview & Entity-Relationship Diagram")
    lines.append("")
    lines.append(generate_mermaid_erd(tables))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Database Tables by Domain")
    lines.append("")

    # Map tables into domains
    all_grouped_tables = set()
    for domain_name, table_list in DOMAINS.items():
        lines.append(f"### {domain_name}")
        lines.append("")
        for table_name in table_list:
            if table_name not in tables:
                continue
            all_grouped_tables.add(table_name)
            table = tables[table_name]
            desc = TABLE_DESCRIPTIONS.get(table_name, "Application database table.")
            lines.append(f"#### `{table_name}`")
            lines.append("")
            lines.append(f"*{desc}*")
            lines.append("")

            # Columns table
            lines.append("| Column | Type | Nullable | Default | PK | FK / References |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

            for col in table.columns:
                col_name = col.name
                col_type = f"`{_format_type(col)}`"
                nullable = "YES" if col.nullable else "NO"
                default_val = f"`{_format_default(col)}`" if _format_default(col) != "-" else "-"
                is_pk = "✅" if col.primary_key else "-"

                fks = [f"`{fk.column.table.name}.{fk.column.name}`" for fk in col.foreign_keys]
                fk_str = ", ".join(fks) if fks else "-"

                lines.append(
                    f"| `{col_name}` | {col_type} | {nullable} | "
                    f"{default_val} | {is_pk} | {fk_str} |"
                )

            # Constraints and Indexes
            indexes = sorted(
                [idx for idx in table.indexes if not idx.unique],
                key=lambda idx: idx.name or "",
            )
            unique_constraints = sorted(
                [c for c in table.constraints if isinstance(c, UniqueConstraint)],
                key=lambda c: str(c.name or ""),
            )
            check_constraints = sorted(
                [c for c in table.constraints if isinstance(c, CheckConstraint)],
                key=lambda c: str(c.name or str(c.sqltext)),
            )

            extra_details = []
            if unique_constraints:
                unique_cols = [
                    f"`{', '.join(col.name for col in uc.columns)}`"
                    for uc in unique_constraints
                    if len(uc.columns) > 0
                ]
                if unique_cols:
                    extra_details.append(f"- **Unique Constraints**: {', '.join(unique_cols)}")

            if check_constraints:
                check_strs = [
                    f"`{cc.name}` (`{cc.sqltext}`)" if cc.name else f"`{cc.sqltext}`"
                    for cc in check_constraints
                ]
                extra_details.append(f"- **Check Constraints**: {', '.join(check_strs)}")

            if indexes:
                idx_strs = [
                    f"`{idx.name}` on `{', '.join(col.name for col in idx.columns)}`"
                    for idx in indexes
                ]
                extra_details.append(f"- **Indexes**: {', '.join(idx_strs)}")

            if extra_details:
                lines.append("")
                lines.extend(extra_details)

            lines.append("")

    # Any remaining unclassified tables
    remaining = [t for t in sorted(tables.keys()) if t not in all_grouped_tables]
    if remaining:
        lines.append("### Other Tables")
        lines.append("")
        for table_name in remaining:
            table = tables[table_name]
            lines.append(f"#### `{table_name}`")
            lines.append("")
            lines.append("| Column | Type | Nullable | Default | PK | FK |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for col in table.columns:
                fks = [f"`{fk.column.table.name}.{fk.column.name}`" for fk in col.foreign_keys]
                fk_str = ", ".join(fks) if fks else "-"
                lines.append(
                    f"| `{col.name}` | `{_format_type(col)}` | {'YES' if col.nullable else 'NO'} | "
                    f"`{_format_default(col)}` | {'✅' if col.primary_key else '-'} | {fk_str} |"
                )
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Automated Verification & Updates")
    lines.append("")
    lines.append(
        "This document is verified continuously in CI via `backend/tests/test_schema_docs.py`."
    )
    lines.append("To regenerate this document after creating or modifying SQLAlchemy models:")
    lines.append("")
    lines.append("```bash")
    lines.append("python backend/scripts/generate_schema_docs.py")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate database schema documentation.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs/DATABASE_SCHEMA.md is up to date without writing.",
    )
    args = parser.parse_args()

    content = generate_schema_markdown()

    if args.check:
        if not DOCS_PATH.exists():
            print(f"Error: {DOCS_PATH} does not exist.", file=sys.stderr)
            return 1
        current = DOCS_PATH.read_text(encoding="utf-8")
        if current != content:
            print(
                f"Error: {DOCS_PATH} is out of date with SQLAlchemy models. "
                "Run python backend/scripts/generate_schema_docs.py to update it.",
                file=sys.stderr,
            )
            return 1
        print(f"Success: {DOCS_PATH} is up to date.")
        return 0

    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.write_text(content, encoding="utf-8")
    print(f"Generated database schema documentation at {DOCS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
