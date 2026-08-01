"""Phase 2 — domain and database.

Creates every entity the workflow needs: ownership, product workflows, the
preserved original idea and its revisions, research runs/evidence/keyword
clusters, concepts and versioned design prompts, artwork jobs and assets,
approval history, production jobs, listing drafts, the provider-usage ledger,
the audit log and workflow failures.

Enum types are created once at the top of ``upgrade`` because several tables
share them; every column below therefore uses ``create_type=False``. The
downgrade drops the tables and then the types, so a clean database can be
rebuilt from either direction.

Revision ID: 0002_phase_2_domain
Revises: 0001_baseline
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase_2_domain"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Enum types shared across tables. Created once, dropped once.
ENUM_TYPES: dict[str, tuple[str, ...]] = {
    "idea_mode": ("market-led", "user-idea", "hybrid"),
    "concept_origin": ("user", "market", "hybrid"),
    "concept_status": ("proposed", "shortlisted", "approved", "rejected", "archived"),
    "run_status": (
        "DRAFT",
        "RESEARCH_QUEUED",
        "RESEARCHING",
        "IDEA_REVIEW",
        "IDEA_APPROVED",
        "ART_QUEUED",
        "ART_GENERATION",
        "ART_REVIEW",
        "ARTWORK_APPROVED",
        "PRODUCTION",
        "IP_REVIEW",
        "LISTING_REVIEW",
        "READY_FOR_ETSY_DRAFT",
        "ETSY_DRAFT_CREATED",
        "PUBLISHED",
        "CANCELLED",
    ),
    "approval_gate": ("IDEA_APPROVAL", "ARTWORK_APPROVAL", "LISTING_APPROVAL"),
    "approval_decision": ("PENDING", "APPROVED", "REJECTED", "REVISION_REQUESTED"),
    "job_status": ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"),
    "risk_level": ("low", "medium", "high", "unknown"),
    "source_type": ("marketplace", "blog", "forum", "api", "trends", "other", "fake"),
    "signal_strength": ("strong", "moderate", "weak", "unknown"),
    "competition_level": ("saturated", "crowded", "differentiable", "thin", "unknown"),
    "seasonality": ("evergreen", "seasonal", "both", "unknown"),
    "confidence_level": ("high", "medium", "low"),
    "provider_name": ("fake", "openai", "recraft", "etsy", "uspto"),
    "cost_status": ("estimated", "reconciled", "voided"),
    "audit_action": (
        "entity_created",
        "idea_revised",
        "workflow_transition",
        "approval_decision",
        "cost_recorded",
        "job_status_changed",
        "failure_recorded",
        "retry_scheduled",
        "archived",
    ),
}


def _create_enum_types() -> None:
    for name, values in ENUM_TYPES.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind(), checkfirst=True)


def _drop_enum_types() -> None:
    for name, values in ENUM_TYPES.items():
        postgresql.ENUM(*values, name=name).drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    _create_enum_types()
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "product_workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "idea_mode",
            postgresql.ENUM(
                "market-led", "user-idea", "hybrid", name="idea_mode", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_marketplace", sa.String(length=50), nullable=False),
        sa.Column("target_country", sa.String(length=2), nullable=False),
        sa.Column("output_language", sa.String(length=10), nullable=False),
        sa.Column("target_buyer", sa.Text(), nullable=True),
        sa.Column("intended_product_uses", sa.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(
                "DRAFT",
                "RESEARCH_QUEUED",
                "RESEARCHING",
                "IDEA_REVIEW",
                "IDEA_APPROVED",
                "ART_QUEUED",
                "ART_GENERATION",
                "ART_REVIEW",
                "ARTWORK_APPROVED",
                "PRODUCTION",
                "IP_REVIEW",
                "LISTING_REVIEW",
                "READY_FOR_ETSY_DRAFT",
                "ETSY_DRAFT_CREATED",
                "PUBLISHED",
                "CANCELLED",
                name="run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_product_workflows_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_workflows")),
    )
    op.create_index(
        "ix_product_workflows_created_at", "product_workflows", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_product_workflows_owner_id"), "product_workflows", ["owner_id"], unique=False
    )
    op.create_index(
        "ix_product_workflows_owner_state", "product_workflows", ["owner_id", "state"], unique=False
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column(
            "gate",
            postgresql.ENUM(
                "IDEA_APPROVAL",
                "ARTWORK_APPROVAL",
                "LISTING_APPROVAL",
                name="approval_gate",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "decision",
            postgresql.ENUM(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "REVISION_REQUESTED",
                name="approval_decision",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("revision_request", sa.Text(), nullable=True),
        sa.Column(
            "previous_state",
            postgresql.ENUM(
                "DRAFT",
                "RESEARCH_QUEUED",
                "RESEARCHING",
                "IDEA_REVIEW",
                "IDEA_APPROVED",
                "ART_QUEUED",
                "ART_GENERATION",
                "ART_REVIEW",
                "ARTWORK_APPROVED",
                "PRODUCTION",
                "IP_REVIEW",
                "LISTING_REVIEW",
                "READY_FOR_ETSY_DRAFT",
                "ETSY_DRAFT_CREATED",
                "PUBLISHED",
                "CANCELLED",
                name="run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "resulting_state",
            postgresql.ENUM(
                "DRAFT",
                "RESEARCH_QUEUED",
                "RESEARCHING",
                "IDEA_REVIEW",
                "IDEA_APPROVED",
                "ART_QUEUED",
                "ART_GENERATION",
                "ART_REVIEW",
                "ARTWORK_APPROVED",
                "PRODUCTION",
                "IP_REVIEW",
                "LISTING_REVIEW",
                "READY_FOR_ETSY_DRAFT",
                "ETSY_DRAFT_CREATED",
                "PUBLISHED",
                "CANCELLED",
                name="run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(length=60), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("target_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(decision <> 'REVISION_REQUESTED') OR (revision_request IS NOT NULL)",
            name=op.f("ck_approvals_revision_requires_request_text"),
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_approvals_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
    )
    op.create_index(
        "ix_approvals_workflow_gate_created",
        "approvals",
        ["workflow_id", "gate", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_approvals_workflow_id"), "approvals", ["workflow_id"], unique=False)
    op.create_table(
        "listing_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", sa.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("price_minor_units", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("taxonomy_id", sa.Integer(), nullable=True),
        sa.Column("ai_disclosure", sa.Text(), nullable=True),
        sa.Column("licence_text", sa.Text(), nullable=True),
        sa.Column("customer_instructions", sa.Text(), nullable=True),
        sa.Column("ip_reviewed_phrase", sa.String(length=300), nullable=True),
        sa.Column(
            "ip_risk_level",
            postgresql.ENUM(
                "low", "medium", "high", "unknown", name="risk_level", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("ip_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_acknowledged_by", sa.String(length=200), nullable=True),
        sa.Column("etsy_listing_id", sa.String(length=60), nullable=True),
        sa.Column("etsy_draft_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "cardinality(tags) <= 13", name=op.f("ck_listing_drafts_listing_tag_limit")
        ),
        sa.CheckConstraint(
            "price_minor_units IS NULL OR price_minor_units >= 0",
            name=op.f("ck_listing_drafts_listing_price_non_negative"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_listing_drafts_listing_version_positive")),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_listing_drafts_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing_drafts")),
        sa.UniqueConstraint("etsy_listing_id", name="uq_listing_draft_etsy_listing_id"),
        sa.UniqueConstraint("workflow_id", name=op.f("uq_listing_drafts_workflow_id")),
    )
    op.create_table(
        "original_ideas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("slogan", sa.String(length=300), nullable=True),
        sa.Column("desired_style", sa.String(length=300), nullable=True),
        sa.Column("audience", sa.String(length=300), nullable=True),
        sa.Column("occasion", sa.String(length=200), nullable=True),
        sa.Column("season", sa.String(length=100), nullable=True),
        sa.Column("product_uses", sa.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("revision_count", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "length(original_text) >= 3", name=op.f("ck_original_ideas_original_text_not_trivial")
        ),
        sa.CheckConstraint(
            "revision_count >= 0", name=op.f("ck_original_ideas_revision_count_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_original_ideas_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_original_ideas")),
        sa.UniqueConstraint("workflow_id", name=op.f("uq_original_ideas_workflow_id")),
    )
    op.create_table(
        "research_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                name="job_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("query_angles", sa.ARRAY(sa.String(length=60)), nullable=False),
        sa.Column(
            "confidence",
            postgresql.ENUM("high", "medium", "low", name="confidence_level", create_type=False),
            nullable=False,
        ),
        sa.Column("proposed_test", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint("run_number >= 1", name=op.f("ck_research_runs_run_number_positive")),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_research_runs_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_runs")),
    )
    op.create_index(
        op.f("ix_research_runs_workflow_id"), "research_runs", ["workflow_id"], unique=False
    )
    op.create_index(
        "ix_research_runs_workflow_number",
        "research_runs",
        ["workflow_id", "run_number"],
        unique=True,
    )
    op.create_table(
        "workflow_failures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("failure_state", sa.String(length=60), nullable=False),
        sa.Column("stage", sa.String(length=60), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("error_kind", sa.String(length=60), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt >= 1", name=op.f("ck_workflow_failures_failure_attempt_positive")
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_workflow_failures_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_failures")),
    )
    op.create_index(
        "ix_workflow_failures_workflow_created",
        "workflow_failures",
        ["workflow_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_failures_workflow_id"), "workflow_failures", ["workflow_id"], unique=False
    )
    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_state",
            postgresql.ENUM(
                "DRAFT",
                "RESEARCH_QUEUED",
                "RESEARCHING",
                "IDEA_REVIEW",
                "IDEA_APPROVED",
                "ART_QUEUED",
                "ART_GENERATION",
                "ART_REVIEW",
                "ARTWORK_APPROVED",
                "PRODUCTION",
                "IP_REVIEW",
                "LISTING_REVIEW",
                "READY_FOR_ETSY_DRAFT",
                "ETSY_DRAFT_CREATED",
                "PUBLISHED",
                "CANCELLED",
                name="run_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_state",
            postgresql.ENUM(
                "DRAFT",
                "RESEARCH_QUEUED",
                "RESEARCHING",
                "IDEA_REVIEW",
                "IDEA_APPROVED",
                "ART_QUEUED",
                "ART_GENERATION",
                "ART_REVIEW",
                "ARTWORK_APPROVED",
                "PRODUCTION",
                "IP_REVIEW",
                "LISTING_REVIEW",
                "READY_FOR_ETSY_DRAFT",
                "ETSY_DRAFT_CREATED",
                "PUBLISHED",
                "CANCELLED",
                name="run_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_workflow_transitions_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_transitions")),
    )
    op.create_index(
        "ix_workflow_transitions_workflow_created",
        "workflow_transitions",
        ["workflow_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_transitions_workflow_id"),
        "workflow_transitions",
        ["workflow_id"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column(
            "action",
            postgresql.ENUM(
                "entity_created",
                "idea_revised",
                "workflow_transition",
                "approval_decision",
                "cost_recorded",
                "job_status_changed",
                "failure_recorded",
                "retry_scheduled",
                "archived",
                name="audit_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("correlation_id", sa.String(length=80), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["approval_id"],
            ["approvals.id"],
            name=op.f("fk_audit_events_approval_id_approvals"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_audit_events_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_action_created", "audit_events", ["action", "created_at"], unique=False
    )
    op.create_index(
        "ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"], unique=False
    )
    op.create_index(
        "ix_audit_events_workflow_created",
        "audit_events",
        ["workflow_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_workflow_id"), "audit_events", ["workflow_id"], unique=False
    )
    op.create_table(
        "keyword_clusters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("primary_phrase", sa.String(length=300), nullable=False),
        sa.Column("attributes", sa.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("recipient_occasion_terms", sa.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("use_case_terms", sa.ARRAY(sa.String(length=120)), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column(
            "competition_level",
            postgresql.ENUM(
                "saturated",
                "crowded",
                "differentiable",
                "thin",
                "unknown",
                name="competition_level",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("competition_note", sa.Text(), nullable=True),
        sa.Column("relevance_rank", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relevance_rank >= 0 AND relevance_rank <= 100",
            name=op.f("ck_keyword_clusters_relevance_rank_range"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_runs.id"],
            name=op.f("fk_keyword_clusters_run_id_research_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_clusters")),
    )
    op.create_index(
        op.f("ix_keyword_clusters_run_id"), "keyword_clusters", ["run_id"], unique=False
    )
    op.create_index(
        "ix_keyword_clusters_run_rank",
        "keyword_clusters",
        ["run_id", "relevance_rank"],
        unique=False,
    )
    op.create_table(
        "original_idea_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idea_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revised_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("slogan", sa.String(length=300), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_number >= 1", name=op.f("ck_original_idea_revisions_revision_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["idea_id"],
            ["original_ideas.id"],
            name=op.f("fk_original_idea_revisions_idea_id_original_ideas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_original_idea_revisions")),
        sa.UniqueConstraint("idea_id", "revision_number", name="uq_idea_revision_number"),
    )
    op.create_index(
        op.f("ix_original_idea_revisions_idea_id"),
        "original_idea_revisions",
        ["idea_id"],
        unique=False,
    )
    op.create_table(
        "product_concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("original_idea_id", sa.Uuid(), nullable=True),
        sa.Column("research_run_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "origin",
            postgresql.ENUM("user", "market", "hybrid", name="concept_origin", create_type=False),
            nullable=False,
        ),
        sa.Column("differentiation", sa.Text(), nullable=False),
        sa.Column("target_buyer", sa.Text(), nullable=True),
        sa.Column("buyer_use_case", sa.Text(), nullable=True),
        sa.Column("bundle_potential", sa.Text(), nullable=True),
        sa.Column("intended_product_uses", sa.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column(
            "seasonality",
            postgresql.ENUM(
                "evergreen", "seasonal", "both", "unknown", name="seasonality", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "risk_level",
            postgresql.ENUM(
                "low", "medium", "high", "unknown", name="risk_level", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("risk_note", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score_explanation", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "proposed",
                "shortlisted",
                "approved",
                "rejected",
                "archived",
                name="concept_status",
                create_type=False,
            ),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "length(differentiation) > 0",
            name=op.f("ck_product_concepts_differentiation_not_empty"),
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 1.00 AND score <= 5.00)",
            name=op.f("ck_product_concepts_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["original_idea_id"],
            ["original_ideas.id"],
            name=op.f("fk_product_concepts_original_idea_id_original_ideas"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["research_runs.id"],
            name=op.f("fk_product_concepts_research_run_id_research_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_product_concepts_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_concepts")),
    )
    op.create_index(
        op.f("ix_product_concepts_original_idea_id"),
        "product_concepts",
        ["original_idea_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_concepts_workflow_id"), "product_concepts", ["workflow_id"], unique=False
    )
    op.create_index(
        "ix_product_concepts_workflow_score",
        "product_concepts",
        ["workflow_id", "score"],
        unique=False,
    )
    op.create_index(
        "ix_product_concepts_workflow_status",
        "product_concepts",
        ["workflow_id", "status"],
        unique=False,
    )
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("search_query", sa.Text(), nullable=False),
        sa.Column("query_angle", sa.String(length=60), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "marketplace",
                "blog",
                "forum",
                "api",
                "trends",
                "other",
                "fake",
                name="source_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("inference", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column(
            "seasonality_signal",
            postgresql.ENUM(
                "evergreen", "seasonal", "both", "unknown", name="seasonality", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "competition_signal",
            postgresql.ENUM(
                "saturated",
                "crowded",
                "differentiable",
                "thin",
                "unknown",
                name="competition_level",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "buyer_intent_signal",
            postgresql.ENUM(
                "strong", "moderate", "weak", "unknown", name="signal_strength", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            postgresql.ENUM("high", "medium", "low", name="confidence_level", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(observation) > 0", name=op.f("ck_research_evidence_observation_not_empty")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_runs.id"],
            name=op.f("fk_research_evidence_run_id_research_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_evidence")),
    )
    op.create_index(
        "ix_research_evidence_run_angle",
        "research_evidence",
        ["run_id", "query_angle"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_evidence_run_id"), "research_evidence", ["run_id"], unique=False
    )
    op.create_table(
        "design_prompts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("positive_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("typography_instructions", sa.Text(), nullable=True),
        sa.Column("exact_slogan", sa.String(length=300), nullable=True),
        sa.Column("intended_product_uses", sa.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("style_notes", sa.Text(), nullable=True),
        sa.Column("palette", sa.Text(), nullable=True),
        sa.Column("post_generation_checklist", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(negative_prompt) > 0", name=op.f("ck_design_prompts_negative_prompt_not_empty")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_design_prompts_prompt_version_positive")),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["product_concepts.id"],
            name=op.f("fk_design_prompts_concept_id_product_concepts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_design_prompts")),
        sa.UniqueConstraint("concept_id", "version", name="uq_design_prompt_version"),
    )
    op.create_index(
        op.f("ix_design_prompts_concept_id"), "design_prompts", ["concept_id"], unique=False
    )
    op.create_table(
        "artwork_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "fake",
                "openai",
                "recraft",
                "etsy",
                "uspto",
                name="provider_name",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_model", sa.String(length=120), nullable=True),
        sa.Column("provider_job_id", sa.String(length=200), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                name="job_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("requested_width", sa.Integer(), nullable=True),
        sa.Column("requested_height", sa.Integer(), nullable=True),
        sa.Column("quality", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_kind", sa.String(length=60), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "attempt_count >= 0", name=op.f("ck_artwork_jobs_attempt_count_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["product_concepts.id"],
            name=op.f("fk_artwork_jobs_concept_id_product_concepts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["design_prompts.id"],
            name=op.f("fk_artwork_jobs_prompt_id_design_prompts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_artwork_jobs_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artwork_jobs")),
        sa.UniqueConstraint("idempotency_key", name="uq_artwork_job_idempotency_key"),
    )
    op.create_index(
        op.f("ix_artwork_jobs_workflow_id"), "artwork_jobs", ["workflow_id"], unique=False
    )
    op.create_index(
        "ix_artwork_jobs_workflow_status", "artwork_jobs", ["workflow_id", "status"], unique=False
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("artwork_job_id", sa.Uuid(), nullable=True),
        sa.Column("derived_from_id", sa.Uuid(), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("has_alpha", sa.Boolean(), nullable=True),
        sa.Column("has_transparent_pixels", sa.Boolean(), nullable=True),
        sa.Column("quality_check", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.CheckConstraint("byte_size > 0", name=op.f("ck_assets_asset_byte_size_positive")),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64", name=op.f("ck_assets_checksum_is_sha256")
        ),
        sa.ForeignKeyConstraint(
            ["artwork_job_id"],
            ["artwork_jobs.id"],
            name=op.f("fk_assets_artwork_job_id_artwork_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["derived_from_id"],
            ["assets.id"],
            name=op.f("fk_assets_derived_from_id_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_assets_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("workflow_id", "checksum_sha256", name="uq_asset_workflow_checksum"),
    )
    op.create_index("ix_assets_checksum", "assets", ["checksum_sha256"], unique=False)
    op.create_index(op.f("ix_assets_workflow_id"), "assets", ["workflow_id"], unique=False)
    op.create_table(
        "provider_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("artwork_job_id", sa.Uuid(), nullable=True),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "fake",
                "openai",
                "recraft",
                "etsy",
                "uspto",
                name="provider_name",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("input_units", sa.BigInteger(), nullable=False),
        sa.Column("output_units", sa.BigInteger(), nullable=False),
        sa.Column("unit_kind", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("estimated_cost_minor", sa.BigInteger(), nullable=False),
        sa.Column("actual_cost_minor", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "estimated", "reconciled", "voided", name="cost_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("price_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
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
        sa.CheckConstraint(
            "(status <> 'reconciled') OR (actual_cost_minor IS NOT NULL)",
            name=op.f("ck_provider_usage_reconciled_requires_actual_cost"),
        ),
        sa.CheckConstraint(
            "actual_cost_minor IS NULL OR actual_cost_minor >= 0",
            name=op.f("ck_provider_usage_actual_cost_non_negative"),
        ),
        sa.CheckConstraint(
            "estimated_cost_minor >= 0", name=op.f("ck_provider_usage_estimated_cost_non_negative")
        ),
        sa.CheckConstraint(
            "input_units >= 0", name=op.f("ck_provider_usage_input_units_non_negative")
        ),
        sa.CheckConstraint(
            "output_units >= 0", name=op.f("ck_provider_usage_output_units_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["artwork_job_id"],
            ["artwork_jobs.id"],
            name=op.f("fk_provider_usage_artwork_job_id_artwork_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_provider_usage_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_usage")),
    )
    op.create_index(
        "ix_provider_usage_idempotency_key", "provider_usage", ["idempotency_key"], unique=False
    )
    op.create_index(
        "ix_provider_usage_provider_created",
        "provider_usage",
        ["provider", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_provider_usage_workflow_created",
        "provider_usage",
        ["workflow_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_usage_workflow_id"), "provider_usage", ["workflow_id"], unique=False
    )
    op.create_table(
        "production_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("output_asset_id", sa.Uuid(), nullable=True),
        sa.Column("operations", sa.ARRAY(sa.String(length=60)), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "QUEUED",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                "CANCELLED",
                name="job_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("qa_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("qa_passed", sa.Boolean(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_kind", sa.String(length=60), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "attempt_count >= 0", name=op.f("ck_production_jobs_production_attempt_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["output_asset_id"],
            ["assets.id"],
            name=op.f("fk_production_jobs_output_asset_id_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_production_jobs_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["product_workflows.id"],
            name=op.f("fk_production_jobs_workflow_id_product_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_jobs")),
        sa.UniqueConstraint("idempotency_key", name="uq_production_job_idempotency_key"),
    )
    op.create_index(
        op.f("ix_production_jobs_workflow_id"), "production_jobs", ["workflow_id"], unique=False
    )
    op.create_index(
        "ix_production_jobs_workflow_status",
        "production_jobs",
        ["workflow_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_production_jobs_workflow_status", table_name="production_jobs")
    op.drop_index(op.f("ix_production_jobs_workflow_id"), table_name="production_jobs")
    op.drop_table("production_jobs")
    op.drop_index(op.f("ix_provider_usage_workflow_id"), table_name="provider_usage")
    op.drop_index("ix_provider_usage_workflow_created", table_name="provider_usage")
    op.drop_index("ix_provider_usage_provider_created", table_name="provider_usage")
    op.drop_index("ix_provider_usage_idempotency_key", table_name="provider_usage")
    op.drop_table("provider_usage")
    op.drop_index(op.f("ix_assets_workflow_id"), table_name="assets")
    op.drop_index("ix_assets_checksum", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_artwork_jobs_workflow_status", table_name="artwork_jobs")
    op.drop_index(op.f("ix_artwork_jobs_workflow_id"), table_name="artwork_jobs")
    op.drop_table("artwork_jobs")
    op.drop_index(op.f("ix_design_prompts_concept_id"), table_name="design_prompts")
    op.drop_table("design_prompts")
    op.drop_index(op.f("ix_research_evidence_run_id"), table_name="research_evidence")
    op.drop_index("ix_research_evidence_run_angle", table_name="research_evidence")
    op.drop_table("research_evidence")
    op.drop_index("ix_product_concepts_workflow_status", table_name="product_concepts")
    op.drop_index("ix_product_concepts_workflow_score", table_name="product_concepts")
    op.drop_index(op.f("ix_product_concepts_workflow_id"), table_name="product_concepts")
    op.drop_index(op.f("ix_product_concepts_original_idea_id"), table_name="product_concepts")
    op.drop_table("product_concepts")
    op.drop_index(op.f("ix_original_idea_revisions_idea_id"), table_name="original_idea_revisions")
    op.drop_table("original_idea_revisions")
    op.drop_index("ix_keyword_clusters_run_rank", table_name="keyword_clusters")
    op.drop_index(op.f("ix_keyword_clusters_run_id"), table_name="keyword_clusters")
    op.drop_table("keyword_clusters")
    op.drop_index(op.f("ix_audit_events_workflow_id"), table_name="audit_events")
    op.drop_index("ix_audit_events_workflow_created", table_name="audit_events")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_action_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_workflow_transitions_workflow_id"), table_name="workflow_transitions")
    op.drop_index("ix_workflow_transitions_workflow_created", table_name="workflow_transitions")
    op.drop_table("workflow_transitions")
    op.drop_index(op.f("ix_workflow_failures_workflow_id"), table_name="workflow_failures")
    op.drop_index("ix_workflow_failures_workflow_created", table_name="workflow_failures")
    op.drop_table("workflow_failures")
    op.drop_index("ix_research_runs_workflow_number", table_name="research_runs")
    op.drop_index(op.f("ix_research_runs_workflow_id"), table_name="research_runs")
    op.drop_table("research_runs")
    op.drop_table("original_ideas")
    op.drop_table("listing_drafts")
    op.drop_index(op.f("ix_approvals_workflow_id"), table_name="approvals")
    op.drop_index("ix_approvals_workflow_gate_created", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_product_workflows_owner_state", table_name="product_workflows")
    op.drop_index(op.f("ix_product_workflows_owner_id"), table_name="product_workflows")
    op.drop_index("ix_product_workflows_created_at", table_name="product_workflows")
    op.drop_table("product_workflows")
    op.drop_table("users")
    _drop_enum_types()
