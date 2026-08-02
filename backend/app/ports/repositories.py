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
from typing import Protocol, runtime_checkable

from app.domain.enums import AuditAction, CostStatus, ProviderName
from app.domain.money import Money
from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus
from app.infrastructure.models import (
    Approval,
    AuditEvent,
    DesignPrompt,
    OriginalIdea,
    OriginalIdeaRevision,
    OwnerSettings,
    ProductConcept,
    ProductWorkflow,
    ProviderCredential,
    ProviderUsage,
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
