"""Application service for Listing Draft lifecycle, updates, and Gate 3 decisions."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from typing import Any
import uuid
import structlog

from app.application.package import CustomerPackageService
from app.application.trademark import TrademarkScreeningService
from app.application.unit_of_work import UnitOfWork
from app.domain.enums import AuditAction
from app.domain.errors import DomainError, EntityNotFoundError
from app.domain.tags import validate_listing_title, validate_tags
from app.domain.workflow import (
    ApprovalDecision,
    ApprovalGate,
    RiskLevel,
    RunStatus,
)
from app.infrastructure.models import (
    Approval,
    AuditEvent,
    ListingDraft,
    OutboxMessage,
    ProductWorkflow,
)

logger = structlog.get_logger(__name__)


def deduplicate_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate version history by content so identical title/desc/tags are never duplicated."""
    seen_content: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for item in history:
        raw_t = [str(x).strip().lower() for x in item.get("tags", [])]
        tags_sorted = tuple(sorted(raw_t))
        content_key = f"{str(item.get('title', '')).strip().lower()}||{str(item.get('description', '')).strip().lower()}||{','.join(tags_sorted)}"
        if content_key not in seen_content:
            seen_content.add(content_key)
            cleaned.append(item)
    return cleaned


def record_version_snapshot(draft: ListingDraft, source: str = "manual") -> None:
    """Record a version snapshot into draft.ip_findings['history'] and ensure no duplicates."""
    findings = dict(draft.ip_findings or {})
    raw_history = findings.get("history")
    history: list[dict[str, Any]] = list(raw_history) if isinstance(raw_history, list) else []

    # Clean existing duplicates first
    history = deduplicate_history(history)

    risk_str = draft.ip_risk_level.value if hasattr(draft.ip_risk_level, "value") else str(draft.ip_risk_level)

    # Check if this exact content already exists in history
    draft_tags_sorted = tuple(sorted(str(t).strip().lower() for t in draft.tags))
    draft_key = f"{str(draft.title).strip().lower()}||{str(draft.description).strip().lower()}||{','.join(draft_tags_sorted)}"

    for existing in history:
        ext_tags_sorted = tuple(sorted(str(t).strip().lower() for t in existing.get("tags", [])))
        ext_key = f"{str(existing.get('title', '')).strip().lower()}||{str(existing.get('description', '')).strip().lower()}||{','.join(ext_tags_sorted)}"
        if ext_key == draft_key:
            # Already exists in history; update version number and avoid adding duplicate
            existing["version"] = draft.version
            existing["ip_risk_level"] = risk_str
            findings["history"] = history
            draft.ip_findings = findings
            return

    snapshot: dict[str, Any] = {
        "version": draft.version,
        "title": draft.title,
        "description": draft.description,
        "tags": list(draft.tags),
        "ip_risk_level": risk_str,
        "created_at": datetime.now(UTC).isoformat(),
        "source": source,
    }
    history.append(snapshot)
    findings["history"] = deduplicate_history(history)

    # Accumulate all historical tags for this draft into tag_history
    raw_tag_history = findings.get("tag_history")
    tag_history: list[str] = list(raw_tag_history) if isinstance(raw_tag_history, list) else []
    seen_tags = set(tag_history)
    for t in draft.tags:
        clean = str(t).strip().lower()
        if clean and clean not in seen_tags:
            seen_tags.add(clean)
            tag_history.append(clean)
    findings["tag_history"] = tag_history

    draft.ip_findings = findings


class ListingDraftService:
    """Orchestrates Etsy listing draft edits, trademark re-screening, and Gate 3 approvals."""

    async def get_or_create_listing(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> ListingDraft:
        """Fetch active listing draft or initialize default from workflow concepts."""
        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is not None:
            return draft

        workflow = await uow.workflows.get(workflow_id)
        if workflow is None:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        # Initialize default listing copy from workflow context
        initial_title = f"{workflow.name[:90]} PNG Digital Download Sublimation Design"[:140]

        words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", workflow.name) if len(w) > 2]
        niche_words = [w for w in words if w not in {"the", "and", "for", "with", "workflow", "campaign", "concept"}]
        main_niche = " ".join(niche_words[:2]) if niche_words else ""

        candidate_tags = []
        if main_niche:
            candidate_tags.extend([
                f"{main_niche[:16]} png"[:20],
                f"{main_niche[:12]} sublimation"[:20],
                f"{main_niche[:13]} clipart"[:20],
            ])
        candidate_tags.extend([
            "png digital download",
            "sublimation design",
            "tshirt graphic",
            "transparent png",
            "printable art",
            "clipart graphic",
            "instant download",
            "tshirt design png",
            "commercial use png",
            "pod graphics",
            "mug design download",
            "sticker png",
            "digital craft file",
        ])

        seen: set[str] = set()
        initial_tags: list[str] = []
        for t in candidate_tags:
            clean = t.strip().lower()
            if clean and clean not in seen:
                seen.add(clean)
                initial_tags.append(clean)
            if len(initial_tags) == 13:
                break

        from app.domain.taxonomy_resolver import EtsyTaxonomyResolver
        tax_res = EtsyTaxonomyResolver().resolve(title=initial_title, tags=initial_tags)

        draft = ListingDraft(
            workflow_id=workflow_id,
            title=initial_title,
            description="High-resolution digital PNG download (4500x5400 px @ 300 DPI, transparent background).",
            tags=initial_tags,
            taxonomy_id=tax_res.taxonomy_id,
            taxonomy_path=tax_res.taxonomy_path,
            ip_risk_level=RiskLevel.UNKNOWN,
            ip_findings={},
            version=1,
        )
        record_version_snapshot(draft, source="initial")
        await uow.listing_drafts.add(draft)
        return draft

    async def update_listing_draft(
        self,
        workflow_id: uuid.UUID,
        *,
        title: str,
        description: str,
        tags: list[str],
        taxonomy_id: int | None = None,
        taxonomy_path: str | None = None,
        expected_version: int | None,
        uow: UnitOfWork,
        actor_email: str,
        trademark_service: TrademarkScreeningService | None = None,
    ) -> ListingDraft:
        """Update listing title, description, tags, and category with strict validation and optimistic concurrency."""
        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", workflow_id)

        # Validate title
        is_title_valid, title_err = validate_listing_title(title)
        if not is_title_valid:
            raise DomainError(title_err or "Invalid listing title.")

        # Validate tags
        is_tags_valid, accepted_tags, tag_errors = validate_tags(tags)
        if not is_tags_valid:
            raise DomainError(f"Tag validation failed: {'; '.join(tag_errors)}")

        updated_draft = await uow.listing_drafts.update(
            draft.id,
            title=title.strip(),
            description=description.strip(),
            tags=accepted_tags,
            taxonomy_id=taxonomy_id,
            taxonomy_path=taxonomy_path,
            expected_version=expected_version,
        )

        # Automatically re-screen trademark risk if service is provided
        if trademark_service is not None:
            concepts = await uow.concepts.list_for_workflow(workflow_id)
            slogan: str | None = None
            if concepts:
                concept = concepts[0]
                prompts = await uow.concepts.prompts(concept.id)
                if prompts:
                    slogan = prompts[-1].exact_slogan

            keywords = accepted_tags[:5] if accepted_tags else []
            risk_level, findings = await trademark_service.screen_listing_trademark(
                slogan=slogan,
                title=updated_draft.title,
                keywords=keywords,
                tags=accepted_tags,
            )

            # Preserve history across re-screens
            raw_history = (updated_draft.ip_findings or {}).get("history")
            findings["history"] = list(raw_history) if isinstance(raw_history, list) else []

            reviewed_phrase = slogan or updated_draft.title
            updated_draft = await uow.listing_drafts.update_ip_review(
                updated_draft.id,
                ip_reviewed_phrase=reviewed_phrase,
                ip_risk_level=risk_level,
                ip_findings=findings,
            )

        # Save snapshot into history
        record_version_snapshot(updated_draft, source="manual")

        # Record audit event
        await uow.audit.record(
            action=AuditAction.SETTINGS_UPDATED,
            entity_type="ListingDraft",
            summary="Updated listing draft copy and tags",
            workflow_id=workflow_id,
            entity_id=draft.id,
            actor=actor_email,
            metadata={
                "action": "update_listing_draft",
                "version": updated_draft.version,
                "title_length": len(updated_draft.title),
                "tags_count": len(updated_draft.tags),
            },
        )

        logger.info(
            "listing_draft_updated",
            workflow_id=str(workflow_id),
            version=updated_draft.version,
        )
        return updated_draft

    async def restore_version(
        self,
        workflow_id: uuid.UUID,
        target_version: int,
        uow: UnitOfWork,
        actor_email: str,
        trademark_service: TrademarkScreeningService | None = None,
    ) -> ListingDraft:
        """Restore listing copy from a previous version snapshot in history."""
        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", workflow_id)

        raw_history = (draft.ip_findings or {}).get("history")
        history: list[dict[str, Any]] = list(raw_history) if isinstance(raw_history, list) else []
        snapshot = next((s for s in history if s.get("version") == target_version), None)
        if not snapshot:
            raise DomainError(f"Version {target_version} not found in listing history.")

        restored_title = str(snapshot.get("title", draft.title))
        restored_description = str(snapshot.get("description", draft.description))
        raw_tags = snapshot.get("tags", draft.tags)
        restored_tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else list(draft.tags)

        return await self.update_listing_draft(
            workflow_id=workflow_id,
            title=restored_title,
            description=restored_description,
            tags=restored_tags,
            expected_version=None,
            uow=uow,
            actor_email=actor_email,
            trademark_service=trademark_service,
        )

    async def delete_version(
        self,
        workflow_id: uuid.UUID,
        target_version: int,
        uow: UnitOfWork,
        actor_email: str,
    ) -> ListingDraft:
        """Delete a version snapshot from listing history."""
        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", workflow_id)

        findings = dict(draft.ip_findings or {})
        raw_history = findings.get("history")
        history: list[dict[str, Any]] = list(raw_history) if isinstance(raw_history, list) else []

        remaining_history = [s for s in history if s.get("version") != target_version]
        if len(remaining_history) == len(history):
            raise DomainError(f"Version {target_version} not found in listing history.")

        findings["history"] = deduplicate_history(remaining_history)
        draft.ip_findings = findings
        await uow.listing_drafts.update_ip_review(
            draft.id,
            ip_reviewed_phrase=draft.ip_reviewed_phrase,
            ip_risk_level=draft.ip_risk_level,
            ip_findings=findings,
        )

        await uow.audit.record(
            action=AuditAction.SETTINGS_UPDATED,
            entity_type="ListingDraft",
            summary=f"Deleted listing version {target_version} from history",
            workflow_id=workflow_id,
            entity_id=draft.id,
            actor=actor_email,
            metadata={"deleted_version": target_version},
        )
        return draft

    async def remove_tag_from_history(
        self,
        workflow_id: uuid.UUID,
        tag: str,
        uow: UnitOfWork,
        actor_email: str,
    ) -> ListingDraft:
        """Permanently remove a tag from this campaign's historical tag list."""
        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", workflow_id)

        findings = dict(draft.ip_findings or {})
        target_tag = tag.strip().lower()
        raw_th = findings.get("tag_history", [])
        if isinstance(raw_th, list):
            findings["tag_history"] = [t for t in raw_th if str(t).strip().lower() != target_tag]
        draft.ip_findings = findings

        await uow.listing_drafts.update_ip_review(
            draft.id,
            ip_reviewed_phrase=draft.ip_reviewed_phrase,
            ip_risk_level=draft.ip_risk_level,
            ip_findings=findings,
        )

        await uow.audit.record(
            action=AuditAction.SETTINGS_UPDATED,
            entity_type="ListingDraft",
            summary=f"Removed tag '{tag}' from campaign tag history",
            workflow_id=workflow_id,
            entity_id=draft.id,
            actor=actor_email,
            metadata={"removed_tag": tag},
        )
        return draft

    async def rescreen_trademark(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
        trademark_service: TrademarkScreeningService,
    ) -> ListingDraft:
        """Trigger on-demand trademark screening for the current listing draft copy."""
        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", workflow_id)

        # Retrieve concept and design prompt for slogan
        concepts = await uow.concepts.list_for_workflow(workflow_id)
        slogan: str | None = None
        if concepts:
            concept = concepts[0]
            prompts = await uow.concepts.prompts(concept.id)
            if prompts:
                slogan = prompts[-1].exact_slogan

        keywords = draft.tags[:5] if draft.tags else []

        risk_level, findings = await trademark_service.screen_listing_trademark(
            slogan=slogan,
            title=draft.title,
            keywords=keywords,
            tags=draft.tags,
        )

        reviewed_phrase = slogan or draft.title
        updated_draft = await uow.listing_drafts.update_ip_review(
            draft.id,
            ip_reviewed_phrase=reviewed_phrase,
            ip_risk_level=risk_level,
            ip_findings=findings,
        )

        logger.info(
            "listing_trademark_rescreened",
            workflow_id=str(workflow_id),
            risk_level=risk_level.value,
        )
        return updated_draft

    async def decide_gate3(
        self,
        workflow_id: uuid.UUID,
        decision: ApprovalDecision,
        acknowledged: bool,
        owner_email: str,
        uow: UnitOfWork,
        package_service: CustomerPackageService,
    ) -> tuple[ProductWorkflow, ListingDraft]:
        """Apply Gate 3 human decision with strict trademark clearance & acknowledgement rules."""
        workflow = await uow.workflows.get(workflow_id)
        if workflow is None:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        draft = await uow.listing_drafts.get_by_workflow(workflow_id)
        if draft is None:
            raise EntityNotFoundError("ListingDraft", workflow_id)

        now = datetime.now(UTC)
        from_state = workflow.state

        if decision == ApprovalDecision.APPROVED:
            # 1. Validate listing fields
            is_title_valid, title_err = validate_listing_title(draft.title)
            if not is_title_valid:
                raise DomainError(f"Cannot approve: {title_err}")

            is_tags_valid, _, tag_errors = validate_tags(draft.tags)
            if not is_tags_valid:
                raise DomainError(f"Cannot approve: {'; '.join(tag_errors)}")

            # 2. Enforce IP Risk rules
            if draft.ip_risk_level == RiskLevel.HIGH:
                raise DomainError(
                    "Gate 3 approval blocked: Listing contains HIGH_RISK trademark matches. "
                    "Please edit the slogan, title, or tags to remove infringing terms and re-screen."
                )

            if draft.ip_risk_level == RiskLevel.MEDIUM:
                if not acknowledged and draft.ip_acknowledged_at is None:
                    raise DomainError(
                        "Gate 3 approval requires explicit acknowledgement of trademark WARNING findings."
                    )
                if acknowledged and draft.ip_acknowledged_at is None:
                    await uow.listing_drafts.acknowledge_ip_risk(
                        draft.id,
                        acknowledged_by=owner_email,
                        acknowledged_at=now,
                    )

            # 3. Build/verify customer package asset
            package_asset = await package_service.build_customer_package(workflow_id, uow)
            if package_asset is None:
                raise DomainError("Failed to verify customer download ZIP package before Gate 3 approval.")

            to_state = RunStatus.READY_FOR_ETSY_DRAFT

        elif decision == ApprovalDecision.REJECTED:
            to_state = RunStatus.ARTWORK_APPROVED

        else:
            raise DomainError(f"Unsupported Gate 3 decision: {decision}")

        # Transition workflow state
        if workflow.state != to_state:
            # If workflow is in an earlier valid state before LISTING_REVIEW, advance through the happy path
            if workflow.state == RunStatus.ARTWORK_APPROVED:
                await uow.workflows.transition(
                    workflow,
                    to_state=RunStatus.PRODUCTION,
                    expected_version=workflow.version,
                    reason="Advance to production pipeline",
                    actor=owner_email,
                )
            if workflow.state == RunStatus.PRODUCTION:
                await uow.workflows.transition(
                    workflow,
                    to_state=RunStatus.IP_REVIEW,
                    expected_version=workflow.version,
                    reason="Advance to IP & trademark review",
                    actor=owner_email,
                )
            if workflow.state == RunStatus.IP_REVIEW:
                await uow.workflows.transition(
                    workflow,
                    to_state=RunStatus.LISTING_REVIEW,
                    expected_version=workflow.version,
                    reason="Advance to listing review",
                    actor=owner_email,
                )

            await uow.workflows.transition(
                workflow,
                to_state=to_state,
                expected_version=workflow.version,
                gate=ApprovalGate.LISTING_APPROVAL,
                decision=decision,
                reason=f"Gate 3 decision: {decision.value}",
                actor=owner_email,
            )

        # Record Approval
        await uow.approvals.record(
            workflow=workflow,
            gate=ApprovalGate.LISTING_APPROVAL,
            decision=decision,
            previous_state=from_state,
            resulting_state=to_state,
            actor=owner_email,
            target_type="ListingDraft",
            target_id=draft.id,
            target_version=draft.version,
            comment=f"Risk: {draft.ip_risk_level.value}. Acknowledged: {acknowledged or draft.ip_acknowledged_at is not None}.",
        )

        # Record Audit Event
        await uow.audit.record(
            action=AuditAction.APPROVAL_DECISION,
            entity_type="ListingDraft",
            summary=f"Gate 3 {decision.value} for listing draft",
            workflow_id=workflow_id,
            entity_id=draft.id,
            actor=owner_email,
            metadata={
                "gate": ApprovalGate.LISTING_APPROVAL.value,
                "decision": decision.value,
                "risk_level": draft.ip_risk_level.value,
                "target_state": to_state.value,
            },
        )

        # Record Outbox Message
        await uow.outbox.add(
            event_type="listing.gate3_decided",
            payload={
                "workflow_id": str(workflow_id),
                "gate": ApprovalGate.LISTING_APPROVAL.value,
                "decision": decision.value,
                "state": to_state.value,
                "actor": owner_email,
            },
        )

        logger.info(
            "gate3_decision_applied",
            workflow_id=str(workflow_id),
            decision=decision.value,
            new_state=workflow.state.value,
        )
        return workflow, draft
