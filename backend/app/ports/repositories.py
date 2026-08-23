"""Repository interfaces.

Use cases depend on these protocols, never on SQLAlchemy. The SQL-backed
implementations live in ``app/infrastructure/repositories``; an in-memory
implementation would satisfy the same contract, which is what makes the use
cases testable without a database.

Note the deliberate gaps: there is no ``update`` on the approval, audit or idea
revision repositories, and no ``delete`` anywhere. Append-only is expressed by
the absence of the method, not by a comment asking callers to behave.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from app.domain.enums import AuditAction, CostStatus, ProviderName
from app.domain.money import Money
from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus
from app.infrastructure.models import (
    Approval,
    ArtworkJob,
    Asset,
    AuditEvent,
    DesignPrompt,
    KeywordCluster,
    ListingDraft,
    OriginalIdea,
    OriginalIdeaRevision,
    OutboxMessage,
    OwnerSettings,
    ProductConcept,
    ProductionJob,
    ProductWorkflow,
    ProviderCredential,
    ProviderUsage,
    ResearchEvidence,
    ResearchRun,
    ShopConnection,
    TelegramConnection,
    TrademarkRecord,
    User,
    UserSession,
    WorkflowTransition,
)


@runtime_checkable
class UserRepository(Protocol):
    """Passwords are hashed above this layer; only hashes cross the boundary."""

    async def add(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str | None = None,
        is_active: bool = True,
        user_id: uuid.UUID | None = None,
    ) -> User: ...

    async def get(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def set_password_hash(self, user: User, password_hash: str) -> User: ...


@runtime_checkable
class SessionRepository(Protocol):
    """Server-side sessions (ADR-0002). Keyed by token *hash*, never the token."""

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        csrf_token: str,
        expires_at: datetime,
        user_agent: str | None = None,
    ) -> UserSession: ...

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None: ...

    async def touch(self, record: UserSession, *, now: datetime) -> None: ...

    async def revoke(self, record: UserSession, *, now: datetime) -> None: ...

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, now: datetime) -> int: ...

    async def active_for_user(
        self, user_id: uuid.UUID, *, now: datetime
    ) -> Sequence[UserSession]: ...


@runtime_checkable
class OwnerSettingsRepository(Protocol):
    async def get_for_user(self, user_id: uuid.UUID) -> OwnerSettings | None: ...

    async def create_defaults(self, user_id: uuid.UUID) -> OwnerSettings: ...

    async def apply(self, settings: OwnerSettings, changes: dict[str, object]) -> OwnerSettings: ...


@runtime_checkable
class ProviderCredentialRepository(Protocol):
    """Ciphertext in, ciphertext out. The key never reaches this layer."""

    async def get(
        self, user_id: uuid.UUID, provider: ProviderName
    ) -> ProviderCredential | None: ...

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[ProviderCredential]: ...

    async def list_stale_key_versions(self, current_version: int) -> Sequence[ProviderCredential]:
        """Rows not yet written under the current key, across all owners."""
        ...

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        provider: ProviderName,
        ciphertext: bytes,
        key_version: int,
        masked_value: str,
        label: str | None = None,
    ) -> tuple[ProviderCredential, bool]:
        """Store or replace. Returns ``(credential, created)``."""
        ...

    async def delete(self, credential: ProviderCredential) -> None: ...


@runtime_checkable
class TelegramConnectionRepository(Protocol):
    async def get_by_user_id(self, user_id: uuid.UUID) -> TelegramConnection | None: ...

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> TelegramConnection | None: ...

    async def create_or_update_pairing_code(
        self,
        *,
        user_id: uuid.UUID,
        code_hash: str,
        expires_at: datetime,
    ) -> TelegramConnection: ...

    async def get_by_pairing_code_hash(self, code_hash: str) -> TelegramConnection | None: ...

    async def increment_failed_attempts(self, record: TelegramConnection) -> None: ...

    async def pair(
        self,
        record: TelegramConnection,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_username: str | None,
        paired_at: datetime,
    ) -> None: ...

    async def disconnect(self, record: TelegramConnection, *, revoked_at: datetime) -> None: ...


@runtime_checkable
class ShopConnectionRepository(Protocol):
    async def get_by_user_id(
        self, user_id: uuid.UUID, provider: str = "etsy"
    ) -> ShopConnection | None: ...

    async def get_by_shop_id(
        self, etsy_shop_id: str, provider: str = "etsy"
    ) -> ShopConnection | None: ...

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[ShopConnection]: ...

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        provider: str = "etsy",
        etsy_user_id: str,
        etsy_shop_id: str,
        etsy_shop_name: str,
        ciphertext_access_token: bytes,
        ciphertext_refresh_token: bytes,
        key_version: int,
        token_expires_at: datetime,
        granted_scopes: list[str],
        connection_status: str = "connected",
        last_refreshed_at: datetime | None = None,
    ) -> ShopConnection: ...

    async def update_tokens(
        self,
        record: ShopConnection,
        *,
        ciphertext_access_token: bytes,
        ciphertext_refresh_token: bytes,
        key_version: int,
        token_expires_at: datetime,
        last_refreshed_at: datetime | None = None,
    ) -> ShopConnection: ...

    async def update_status(
        self, record: ShopConnection, *, connection_status: str
    ) -> ShopConnection: ...

    async def delete(self, record: ShopConnection) -> None: ...


@runtime_checkable
class WorkflowRepository(Protocol):
    async def add(self, workflow: ProductWorkflow) -> ProductWorkflow: ...

    async def get(self, workflow_id: uuid.UUID) -> ProductWorkflow | None: ...

    async def list(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        state: RunStatus | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ProductWorkflow]: ...

    async def count(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        state: RunStatus | None = None,
        include_archived: bool = False,
    ) -> int: ...

    async def transition(
        self,
        workflow: ProductWorkflow,
        *,
        to_state: RunStatus,
        expected_version: int,
        reason: str,
        actor: str = "system",
        gate: ApprovalGate | None = None,
        decision: ApprovalDecision | None = None,
    ) -> WorkflowTransition:
        """Compare-and-set state change.

        Raises ``ConcurrentModificationError`` when ``expected_version`` no
        longer matches, and ``IllegalTransitionError`` when the domain refuses
        the move. Writes the transition row; the caller writes the audit event.

        A caller acting on a human decision passes ``gate`` and ``decision``:
        that is the only way to leave a review state, so a gate cannot be
        bypassed by a plain transition.
        """
        ...

    async def record_initial_state(
        self, workflow: ProductWorkflow, *, actor: str = "system"
    ) -> WorkflowTransition:
        """The first timeline row, with a null ``from_state``."""
        ...

    async def transitions(self, workflow_id: uuid.UUID) -> Sequence[WorkflowTransition]: ...


@runtime_checkable
class IdeaRepository(Protocol):
    """The original idea is write-once; revisions are append-only."""

    async def add(self, idea: OriginalIdea) -> OriginalIdea: ...

    async def get_for_workflow(self, workflow_id: uuid.UUID) -> OriginalIdea | None: ...

    async def add_revision(
        self,
        idea: OriginalIdea,
        *,
        revised_text: str,
        slogan: str | None = None,
        note: str | None = None,
        actor: str = "owner",
    ) -> OriginalIdeaRevision:
        """Record a new wording without touching ``original_text``."""
        ...

    async def revisions(self, idea_id: uuid.UUID) -> Sequence[OriginalIdeaRevision]: ...


@runtime_checkable
class ConceptRepository(Protocol):
    async def add(self, concept: ProductConcept) -> ProductConcept: ...

    async def get(self, concept_id: uuid.UUID) -> ProductConcept | None: ...

    async def list_for_workflow(
        self, workflow_id: uuid.UUID, *, include_archived: bool = True
    ) -> Sequence[ProductConcept]: ...

    async def add_prompt_version(
        self,
        concept: ProductConcept,
        *,
        positive_prompt: str,
        negative_prompt: str,
        typography_instructions: str | None = None,
        exact_slogan: str | None = None,
        change_note: str | None = None,
        intended_product_uses: list[str] | None = None,
        style_notes: str | None = None,
        palette: str | None = None,
        post_generation_checklist: list[str] | None = None,
        generation_metadata: dict[str, object] | None = None,
    ) -> DesignPrompt:
        """Append prompt version N+1. Earlier versions are never modified."""
        ...

    async def next_prompt_version(self, concept_id: uuid.UUID) -> int: ...

    async def prompts(self, concept_id: uuid.UUID) -> Sequence[DesignPrompt]: ...


@runtime_checkable
class ApprovalRepository(Protocol):
    """Append-only. There is no update and no delete, by design."""

    async def record(
        self,
        *,
        workflow: ProductWorkflow,
        gate: ApprovalGate,
        decision: ApprovalDecision,
        previous_state: RunStatus,
        resulting_state: RunStatus,
        actor: str,
        target_type: str,
        target_id: uuid.UUID | None = None,
        target_version: int | None = None,
        comment: str | None = None,
        revision_request: str | None = None,
        decided_at: datetime | None = None,
    ) -> Approval: ...

    async def history(
        self, workflow_id: uuid.UUID, *, gate: ApprovalGate | None = None
    ) -> Sequence[Approval]: ...

    async def latest(self, workflow_id: uuid.UUID, gate: ApprovalGate) -> Approval | None: ...

    async def is_approved(self, workflow_id: uuid.UUID, gate: ApprovalGate) -> bool:
        """True only when the *most recent* decision at the gate is APPROVED."""
        ...


@runtime_checkable
class CostRepository(Protocol):
    async def record_estimate(
        self,
        *,
        workflow_id: uuid.UUID,
        provider: ProviderName,
        service: str,
        operation: str,
        estimated: Money,
        input_units: int = 0,
        output_units: int = 0,
        unit_kind: str = "units",
        idempotency_key: str | None = None,
        price_reference: dict[str, object] | None = None,
    ) -> ProviderUsage: ...

    async def reconcile(
        self,
        usage_id: uuid.UUID,
        *,
        actual: Money,
        input_units: int | None = None,
        output_units: int | None = None,
    ) -> ProviderUsage:
        """Replace the estimate with what the provider actually reported."""
        ...

    async def void(self, usage_id: uuid.UUID) -> ProviderUsage:
        """Release a reservation for an operation that never ran."""
        ...

    async def find_by_idempotency_key(self, key: str) -> ProviderUsage | None: ...

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ProviderUsage]: ...

    async def total_by_operation(
        self, workflow_id: uuid.UUID, *, currency: str = "USD"
    ) -> dict[str, Money]: ...

    async def total_for_workflow(
        self, workflow_id: uuid.UUID, *, currency: str = "USD"
    ) -> Money: ...

    async def total_for_provider(
        self,
        provider: ProviderName,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        currency: str = "USD",
    ) -> Money: ...

    async def total_in_period(
        self,
        *,
        since: datetime,
        until: datetime,
        currency: str = "USD",
        status: CostStatus | None = None,
    ) -> Money: ...

    async def total_for_owner_in_period(
        self,
        owner_id: uuid.UUID,
        *,
        since: datetime,
        until: datetime,
        currency: str = "USD",
    ) -> Money: ...

    async def list_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        provider: ProviderName | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[tuple[ProviderUsage, str]]:
        """List provider usage records with their workflow name for an owner."""
        ...

    async def get_owner_metrics(
        self,
        owner_id: uuid.UUID,
        *,
        today_start: datetime,
        month_start: datetime,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Aggregate token counts, costs, and breakdowns for an owner."""
        ...

    async def would_exceed_budget(self, *, current: Money, projected: Money, limit: Money) -> bool:
        """Compare-before-dispatch helper."""
        ...


@runtime_checkable
class AuditRepository(Protocol):
    """Append-only. Entries are never updated or deleted by application flows."""

    async def record(
        self,
        *,
        action: AuditAction,
        entity_type: str,
        summary: str,
        workflow_id: uuid.UUID | None = None,
        entity_id: uuid.UUID | None = None,
        approval_id: uuid.UUID | None = None,
        actor: str = "system",
        correlation_id: str | None = None,
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent: ...

    async def for_workflow(
        self, workflow_id: uuid.UUID, *, limit: int = 200
    ) -> Sequence[AuditEvent]: ...

    async def for_entity(self, entity_type: str, entity_id: uuid.UUID) -> Sequence[AuditEvent]: ...


@runtime_checkable
class OutboxRepository(Protocol):
    async def add(self, event_type: str, payload: dict[str, object]) -> OutboxMessage: ...

    async def get_unprocessed(self, *, limit: int = 100) -> Sequence[OutboxMessage]: ...

    async def mark_processed(self, message_id: uuid.UUID) -> None: ...


@runtime_checkable
class ResearchRepository(Protocol):
    async def add_run(
        self, workflow_id: uuid.UUID, *, idempotency_key: str | None = None
    ) -> ResearchRun: ...

    async def get_run(self, run_id: uuid.UUID) -> ResearchRun | None: ...

    async def get_run_by_idempotency_key(self, key: str) -> ResearchRun | None: ...

    async def get_latest_run(self, workflow_id: uuid.UUID) -> ResearchRun | None: ...

    async def list_runs_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ResearchRun]: ...

    async def update_run(
        self,
        run_id: uuid.UUID,
        *,
        status: object,
        confidence: object | None = None,
        proposed_test: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_reason: str | None = None,
        query_angles: list[str] | None = None,
    ) -> ResearchRun: ...

    async def add_evidence(self, evidence: ResearchEvidence) -> ResearchEvidence: ...

    async def get_evidence_for_run(self, run_id: uuid.UUID) -> Sequence[ResearchEvidence]: ...

    async def add_keyword_cluster(self, cluster: KeywordCluster) -> KeywordCluster: ...

    async def get_keyword_clusters_for_run(self, run_id: uuid.UUID) -> Sequence[KeywordCluster]: ...


@runtime_checkable
class ArtworkJobRepository(Protocol):
    async def add(self, job: ArtworkJob) -> ArtworkJob: ...

    async def get(self, job_id: uuid.UUID) -> ArtworkJob | None: ...

    async def get_by_idempotency_key(self, key: str) -> ArtworkJob | None: ...

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ArtworkJob]: ...

    async def update(
        self,
        job_id: uuid.UUID,
        *,
        status: object,
        provider_job_id: str | None = None,
        attempt_count: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_kind: str | None = None,
        failure_message: str | None = None,
    ) -> ArtworkJob: ...


@runtime_checkable
class AssetRepository(Protocol):
    async def add(self, asset: Asset) -> Asset: ...

    async def get(self, asset_id: uuid.UUID) -> Asset | None: ...

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[Asset]: ...

    async def list_for_job(self, job_id: uuid.UUID) -> Sequence[Asset]: ...

    async def get_by_checksum_sha256(self, workflow_id: uuid.UUID, sha256: str) -> Asset | None: ...

    async def delete(self, asset: Asset) -> None: ...


@runtime_checkable
class ProductionJobRepository(Protocol):
    async def add(self, job: ProductionJob) -> ProductionJob: ...

    async def get(self, job_id: uuid.UUID) -> ProductionJob | None: ...

    async def get_by_idempotency_key(self, key: str) -> ProductionJob | None: ...

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> Sequence[ProductionJob]: ...

    async def get_latest_for_workflow(self, workflow_id: uuid.UUID) -> ProductionJob | None: ...

    async def update(
        self,
        job_id: uuid.UUID,
        *,
        status: object,
        output_asset_id: uuid.UUID | None = None,
        operations: list[str] | None = None,
        attempt_count: int | None = None,
        qa_report: dict[str, object] | None = None,
        qa_passed: bool | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        failure_kind: str | None = None,
        failure_message: str | None = None,
    ) -> ProductionJob: ...


@runtime_checkable
class ListingDraftRepository(Protocol):
    async def add(self, draft: ListingDraft) -> ListingDraft: ...

    async def get(self, draft_id: uuid.UUID) -> ListingDraft | None: ...

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> ListingDraft | None: ...

    async def get_by_workflows(
        self, workflow_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ListingDraft]: ...

    async def update(
        self,
        draft_id: uuid.UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        price_minor_units: int | None = None,
        currency: str | None = None,
        taxonomy_id: int | None = None,
        taxonomy_path: str | None = None,
        quantity: int | None = None,
        sku: str | None = None,
        shop_section_id: str | None = None,
        shop_section_name: str | None = None,
        should_auto_renew: bool | None = None,
        etsy_properties: dict[str, object] | None = None,
        primary_mockup_asset_id: uuid.UUID | None = None,
        shopping_cart_summary: str | None = None,
        ai_disclosure: str | None = None,
        licence_text: str | None = None,
        customer_instructions: str | None = None,
        concept_id: uuid.UUID | None = None,
        concept_version: int | None = None,
        artwork_asset_id: uuid.UUID | None = None,
        listing_context_hash: str | None = None,
        expected_version: int | None = None,
    ) -> ListingDraft: ...

    async def update_ip_review(
        self,
        draft_id: uuid.UUID,
        *,
        ip_reviewed_phrase: str | None,
        ip_risk_level: object,
        ip_findings: dict[str, object],
    ) -> ListingDraft: ...

    async def acknowledge_ip_risk(
        self,
        draft_id: uuid.UUID,
        *,
        acknowledged_by: str,
        acknowledged_at: datetime,
    ) -> ListingDraft: ...

    async def update_etsy_draft(
        self,
        draft_id: uuid.UUID,
        *,
        etsy_shop_id: str,
        etsy_listing_id: str,
        etsy_listing_url: str | None = None,
        etsy_state: str = "draft",
        etsy_draft_created_at: datetime | None = None,
        etsy_dispatch_status: str = "creating_listing",
    ) -> ListingDraft: ...

    async def record_etsy_image_upload(
        self,
        draft_id: uuid.UUID,
        *,
        image_id: str,
    ) -> ListingDraft: ...

    async def record_etsy_file_upload(
        self,
        draft_id: uuid.UUID,
        *,
        file_id: str,
    ) -> ListingDraft: ...

    async def update_etsy_dispatch_status(
        self,
        draft_id: uuid.UUID,
        *,
        status: str,
        failure_reason: str | None = None,
        last_synced_at: datetime | None = None,
    ) -> ListingDraft: ...

    async def clear_etsy_draft_state(
        self,
        draft_id: uuid.UUID,
        *,
        last_synced_at: datetime | None = None,
    ) -> ListingDraft: ...

    async def update_etsy_verification(
        self,
        draft_id: uuid.UUID,
        *,
        status: str,
        verified_at: datetime,
        result: dict[str, object],
    ) -> ListingDraft: ...

    async def list_distinct_shop_sections_for_user(
        self,
        owner_id: uuid.UUID,
    ) -> list[tuple[str | None, str | None]]: ...


@runtime_checkable
class TrademarkRepository(Protocol):
    async def add(self, record: TrademarkRecord) -> TrademarkRecord: ...

    async def get_by_serial(self, serial_number: str) -> TrademarkRecord | None: ...

    async def get_by_registration(self, registration_number: str) -> TrademarkRecord | None: ...

    async def search_by_phrase(
        self, phrase: str, limit: int = 25, live_only: bool | None = None
    ) -> Sequence[TrademarkRecord]: ...

    async def get_latest_source_date(self) -> datetime | None: ...

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> dict[str, int]: ...
