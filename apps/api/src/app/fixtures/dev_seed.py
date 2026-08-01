"""Development seed data.

Creates three workflows, one per idea mode, each far enough along to show the
shape of the domain:

* **market-led** — research run, evidence, keyword clusters, market concepts,
  sitting at the idea gate.
* **user-idea** — an original idea preserved verbatim plus a revision, a concept
  derived from it, two prompt versions, an approved idea gate and cost entries.
* **hybrid** — the owner's idea beside a market concept and a hybrid concept, an
  idea gate that was rejected and then approved, so the append-only history has
  something to show.

Run with::

    python -m app.fixtures.dev_seed

Refuses to run unless ``APP_ENV=local``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import (
    AuditAction,
    CompetitionLevel,
    ConceptOrigin,
    ConceptStatus,
    ConfidenceLevel,
    IdeaMode,
    ProviderName,
    Seasonality,
    SignalStrength,
    SourceType,
)
from app.domain.ideas import normalize_idea_text
from app.domain.money import Money
from app.domain.workflow import (
    ApprovalDecision,
    ApprovalGate,
    JobStatus,
    RiskLevel,
    RunStatus,
)
from app.infrastructure.database import create_engine, create_session_factory
from app.infrastructure.models import (
    KeywordCluster,
    OriginalIdea,
    ProductConcept,
    ProductWorkflow,
    ResearchEvidence,
    ResearchRun,
    User,
)
from app.settings import Settings, get_settings

#: Stamped into every fixture record so development data is obvious in a
#: database, a log line or a screenshot.
DEV_DATA_MARKER = "[DEV FIXTURE — not real market data]"

#: Fixed IDs make the seed idempotent and give tests something to assert on.
FIXTURE_IDS: dict[str, uuid.UUID] = {
    "owner": uuid.UUID("00000000-0000-4000-8000-000000000001"),
    "workflow_market_led": uuid.UUID("00000000-0000-4000-8000-000000000010"),
    "workflow_user_idea": uuid.UUID("00000000-0000-4000-8000-000000000020"),
    "workflow_hybrid": uuid.UUID("00000000-0000-4000-8000-000000000030"),
}

SEED_EPOCH = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)

#: The owner's exact words in the user-idea workflow. Tests assert this string
#: is still readable, character for character, after concepts and revisions
#: exist.
USER_IDEA_TEXT = (
    "A hand-drawn sleepy fox curled around a steaming mug, for people who love "
    "quiet autumn mornings. I want it to feel cosy, not cute-cartoon."
)

HYBRID_IDEA_TEXT = (
    "Something for allotment gardeners — the muddy-boots reality of it, not the "
    "tidy Instagram version."
)


async def _seed_owner(uow: UnitOfWork) -> User:
    existing = await uow.users.get(FIXTURE_IDS["owner"])
    if existing is not None:
        return existing
    owner = User(
        id=FIXTURE_IDS["owner"],
        email="dev-owner@example.invalid",
        display_name=f"Development Owner {DEV_DATA_MARKER}",
    )
    uow.session.add(owner)
    await uow.session.flush()
    return owner


def _evidence(run_id: uuid.UUID, index: int, angle: str) -> ResearchEvidence:
    """A placeholder evidence row.

    ``observation`` says plainly that it is not a real observation. The signal
    columns are qualitative and default to the honest answer rather than an
    invented judgement.
    """
    return ResearchEvidence(
        run_id=run_id,
        search_query=f"example query {index} ({angle})",
        query_angle=angle,
        source_url=f"https://example.invalid/dev-fixture/{angle}/{index}",
        source_title=f"Development fixture source {index}",
        source_type=SourceType.FAKE,
        observation=(
            f"{DEV_DATA_MARKER} Placeholder observation for the '{angle}' angle. "
            "It describes no real listing and contains no sales, search-volume "
            "or revenue figure."
        ),
        inference=(
            f"{DEV_DATA_MARKER} Placeholder inference, clearly separate from the observation above."
        ),
        observed_at=SEED_EPOCH + timedelta(minutes=index),
        market="US",
        language="en",
        seasonality_signal=Seasonality.UNKNOWN,
        competition_signal=CompetitionLevel.UNKNOWN,
        buyer_intent_signal=SignalStrength.UNKNOWN,
        confidence=ConfidenceLevel.LOW,
    )


async def _seed_research(uow: UnitOfWork, workflow: ProductWorkflow) -> ResearchRun:
    run = ResearchRun(
        workflow_id=workflow.id,
        run_number=1,
        status=JobStatus.SUCCEEDED,
        # CLAUDE.md requires at least three distinct buyer-intent angles.
        query_angles=["broad", "long-tail", "occasion", "style", "use-case"],
        confidence=ConfidenceLevel.LOW,
        proposed_test=(
            f"{DEV_DATA_MARKER} Evidence is placeholder data, so confidence is "
            "LOW. Replace with a real research run before drawing any conclusion."
        ),
        started_at=SEED_EPOCH,
        completed_at=SEED_EPOCH + timedelta(minutes=4),
    )
    uow.session.add(run)
    await uow.session.flush()

    for index, angle in enumerate(["broad", "long-tail", "occasion"], start=1):
        uow.session.add(_evidence(run.id, index, angle))

    uow.session.add(
        KeywordCluster(
            run_id=run.id,
            primary_phrase="example primary phrase",
            attributes=["transparent png", "hand drawn"],
            recipient_occasion_terms=["gift", "autumn"],
            use_case_terms=["mug", "tote"],
            market="US",
            language="en",
            competition_level=CompetitionLevel.UNKNOWN,
            competition_note=(
                f"{DEV_DATA_MARKER} No real marketplace was observed, so the "
                "competition level stays UNKNOWN."
            ),
            relevance_rank=50,
        )
    )
    await uow.session.flush()
    return run


def _concept(
    workflow: ProductWorkflow,
    *,
    title: str,
    origin: ConceptOrigin,
    differentiation: str,
    score: str | None,
    original_idea_id: uuid.UUID | None = None,
    research_run_id: uuid.UUID | None = None,
    status: ConceptStatus = ConceptStatus.PROPOSED,
) -> ProductConcept:
    return ProductConcept(
        workflow_id=workflow.id,
        original_idea_id=original_idea_id,
        research_run_id=research_run_id,
        title=title,
        description=f"{DEV_DATA_MARKER} {title}",
        origin=origin,
        differentiation=differentiation,
        target_buyer="Development fixture buyer",
        buyer_use_case="Development fixture use case",
        intended_product_uses=["mug", "tote"],
        seasonality=Seasonality.UNKNOWN,
        risk_level=RiskLevel.UNKNOWN,
        risk_note=(
            f"{DEV_DATA_MARKER} No IP screening was performed. Risk is UNKNOWN, "
            "which is not the same as low."
        ),
        score=Decimal(score) if score is not None else None,
        score_breakdown=(
            {
                "demand": 3,
                "competition_opportunity": 3,
                "seasonal_timing": 3,
                "buyer_clarity": 3,
                "differentiation": 3,
                "product_versatility": 3,
                "ip_safety": 3,
                "note": DEV_DATA_MARKER,
            }
            if score is not None
            else {}
        ),
        score_explanation=(f"{DEV_DATA_MARKER} Placeholder scores. Not derived from evidence."),
        status=status,
    )


async def _add_prompt_versions(uow: UnitOfWork, concept: ProductConcept) -> None:
    """Two versions, so the append-only prompt history has something in it."""
    await uow.concepts.add_prompt_version(
        concept,
        positive_prompt=(
            f"{DEV_DATA_MARKER} Isolated subject on a fully transparent "
            "background, clean uncropped edges, high-resolution print intent, "
            "no text of any kind."
        ),
        negative_prompt=(
            "background, backdrop, scene, mockup, garment, model, watermark, "
            "signature, logo, trademark, copyrighted character, celebrity "
            "likeness, copied artist style, text, letters, misspelled words, "
            "cropped subject, jpeg artifacts, malformed anatomy, low resolution"
        ),
        typography_instructions=None,
        intended_product_uses=["mug", "tote"],
        style_notes=f"{DEV_DATA_MARKER} placeholder style direction",
        palette="muted autumn tones",
        post_generation_checklist=[
            "PNG has an alpha channel with genuinely transparent pixels",
            "no opaque corner pixels or background halo",
            "subject uncropped with the configured safe margin",
            "pixel dimensions recorded as measured, not as requested",
        ],
        generation_metadata={"aspect": "2:3", "quality_tier": "draft"},
        change_note="Initial prompt",
    )
    await uow.concepts.add_prompt_version(
        concept,
        positive_prompt=(
            f"{DEV_DATA_MARKER} As version 1, with a tighter composition and a "
            "clearer focal hierarchy. Still no text."
        ),
        negative_prompt=(
            "background, backdrop, scene, mockup, garment, model, watermark, "
            "signature, logo, trademark, copyrighted character, celebrity "
            "likeness, copied artist style, text, letters, misspelled words, "
            "cropped subject, jpeg artifacts, malformed anatomy, low resolution"
        ),
        typography_instructions=(
            "Render the approved slogan deterministically from an SVG template; "
            "the image model must never produce the text itself."
        ),
        exact_slogan="Slow Mornings",
        intended_product_uses=["mug", "tote"],
        style_notes=f"{DEV_DATA_MARKER} placeholder style direction, refined",
        palette="muted autumn tones",
        post_generation_checklist=[
            "PNG has an alpha channel with genuinely transparent pixels",
            "slogan spelling matches the approved phrase exactly",
        ],
        generation_metadata={"aspect": "2:3", "quality_tier": "final"},
        change_note="Tightened composition; slogan moved to deterministic typography",
    )


async def _seed_market_led(uow: UnitOfWork, owner: User) -> ProductWorkflow:
    """Market-led: no original idea, market concepts, waiting at gate 1."""
    workflow = ProductWorkflow(
        id=FIXTURE_IDS["workflow_market_led"],
        owner_id=owner.id,
        idea_mode=IdeaMode.MARKET_LED,
        name=f"Autumn evergreen exploration {DEV_DATA_MARKER}",
        target_country="US",
        output_language="en",
        target_buyer="Someone buying a small autumn gift",
        intended_product_uses=["mug", "tote", "sticker"],
        state=RunStatus.DRAFT,
        version=1,
    )
    await uow.workflows.add(workflow)
    await uow.workflows.record_initial_state(workflow, actor="fixture")

    run = await _seed_research(uow, workflow)

    for index, title in enumerate(
        ["Market concept A", "Market concept B", "Market concept C"], start=1
    ):
        uow.session.add(
            _concept(
                workflow,
                title=f"{title}",
                origin=ConceptOrigin.MARKET,
                differentiation=f"Placeholder differentiator {index}",
                score=["3.40", "3.10", "2.20"][index - 1],
                research_run_id=run.id,
                # The 2.20 concept is kept, not deleted: a low score never
                # removes a concept.
                status=ConceptStatus.PROPOSED,
            )
        )
    await uow.session.flush()

    # DRAFT → RESEARCH_QUEUED → RESEARCHING → IDEA_REVIEW
    for to_state, reason in [
        (RunStatus.RESEARCH_QUEUED, "research_enqueued"),
        (RunStatus.RESEARCHING, "research_started"),
        (RunStatus.IDEA_REVIEW, "research_completed"),
    ]:
        await uow.workflows.transition(
            workflow,
            to_state=to_state,
            expected_version=workflow.version,
            reason=reason,
            actor="fixture",
        )

    await uow.audit.record(
        action=AuditAction.ENTITY_CREATED,
        entity_type="ProductWorkflow",
        entity_id=workflow.id,
        workflow_id=workflow.id,
        actor="fixture",
        summary=f"{DEV_DATA_MARKER} market-led workflow seeded",
    )
    return workflow


async def _seed_user_idea(uow: UnitOfWork, owner: User) -> ProductWorkflow:
    """User-idea: verbatim idea + revision, derived concept, gate 1 approved."""
    workflow = ProductWorkflow(
        id=FIXTURE_IDS["workflow_user_idea"],
        owner_id=owner.id,
        idea_mode=IdeaMode.USER_IDEA,
        name=f"Sleepy fox mug design {DEV_DATA_MARKER}",
        target_country="GB",
        output_language="en",
        target_buyer="People who like quiet autumn mornings",
        intended_product_uses=["mug", "tote", "card"],
        state=RunStatus.DRAFT,
        version=1,
    )
    await uow.workflows.add(workflow)
    await uow.workflows.record_initial_state(workflow, actor="fixture")

    idea = OriginalIdea(
        workflow_id=workflow.id,
        # Stored exactly as written. Nothing below rewrites this string.
        original_text=USER_IDEA_TEXT,
        normalized_text=normalize_idea_text(USER_IDEA_TEXT),
        slogan="Slow Mornings",
        desired_style="hand-drawn, textured line work",
        audience="adults who buy small comfort gifts",
        occasion="autumn",
        season="autumn",
        product_uses=["mug", "tote", "card"],
    )
    await uow.ideas.add(idea)

    # A correction is a new revision. original_text above is untouched.
    await uow.ideas.add_revision(
        idea,
        revised_text=USER_IDEA_TEXT + " Muted palette, no bright oranges.",
        slogan="Slow Mornings",
        note="Added a palette constraint after seeing the first sketches.",
        actor="fixture",
    )

    concept = _concept(
        workflow,
        title="Sleepy fox, refined",
        origin=ConceptOrigin.USER,
        differentiation=(
            "Texture-led rendering rather than flat vector cuteness, aimed at an adult gift buyer"
        ),
        score="4.10",
        original_idea_id=idea.id,
        status=ConceptStatus.APPROVED,
    )
    await uow.concepts.add(concept)
    await _add_prompt_versions(uow, concept)

    for to_state, reason in [
        (RunStatus.RESEARCH_QUEUED, "research_enqueued"),
        (RunStatus.RESEARCHING, "research_started"),
        (RunStatus.IDEA_REVIEW, "research_completed"),
    ]:
        await uow.workflows.transition(
            workflow,
            to_state=to_state,
            expected_version=workflow.version,
            reason=reason,
            actor="fixture",
        )

    await _decide(
        uow,
        workflow,
        gate=ApprovalGate.IDEA_APPROVAL,
        decision=ApprovalDecision.APPROVED,
        target_type="ProductConcept",
        target_id=concept.id,
        target_version=2,
        comment="Approved for artwork generation.",
    )

    # Two ledger entries: one reconciled, one still an estimate.
    reserved = await uow.costs.record_estimate(
        workflow_id=workflow.id,
        provider=ProviderName.FAKE,
        service="fake-text-1",
        operation="text_synthesis",
        estimated=Money.from_decimal(Decimal("0.00")),
        input_units=1200,
        output_units=400,
        unit_kind="tokens",
        idempotency_key=f"fixture:{workflow.id}:text",
        price_reference={
            "note": DEV_DATA_MARKER,
            "provider": "fake",
            "estimated_output_usd": "0.00",
        },
    )
    await uow.costs.reconcile(reserved.id, actual=Money.from_decimal(Decimal("0.00")))
    await uow.costs.record_estimate(
        workflow_id=workflow.id,
        provider=ProviderName.FAKE,
        service="fake-image-1",
        operation="image_generation",
        estimated=Money.from_decimal(Decimal("0.00")),
        input_units=0,
        output_units=1,
        unit_kind="images",
        idempotency_key=f"fixture:{workflow.id}:image",
        price_reference={"note": DEV_DATA_MARKER, "provider": "fake"},
    )
    await uow.audit.record(
        action=AuditAction.COST_RECORDED,
        entity_type="ProviderUsage",
        workflow_id=workflow.id,
        actor="fixture",
        summary=f"{DEV_DATA_MARKER} fake-provider usage recorded at zero cost",
    )
    return workflow


async def _seed_hybrid(uow: UnitOfWork, owner: User) -> ProductWorkflow:
    """Hybrid: owner idea + market + hybrid concepts, gate rejected then approved."""
    workflow = ProductWorkflow(
        id=FIXTURE_IDS["workflow_hybrid"],
        owner_id=owner.id,
        idea_mode=IdeaMode.HYBRID,
        name=f"Allotment gardener series {DEV_DATA_MARKER}",
        target_country="GB",
        output_language="en",
        target_buyer="Allotment and community-garden holders",
        intended_product_uses=["tshirt", "mug", "sticker"],
        state=RunStatus.DRAFT,
        version=1,
    )
    await uow.workflows.add(workflow)
    await uow.workflows.record_initial_state(workflow, actor="fixture")

    idea = OriginalIdea(
        workflow_id=workflow.id,
        original_text=HYBRID_IDEA_TEXT,
        normalized_text=normalize_idea_text(HYBRID_IDEA_TEXT),
        desired_style="loose ink line work",
        audience="allotment holders",
        occasion=None,
        season="spring",
        product_uses=["tshirt", "mug"],
    )
    await uow.ideas.add(idea)

    run = await _seed_research(uow, workflow)

    # All three origins side by side — the reason hybrid exists.
    for title, origin, score, linked in [
        ("Owner's muddy-boots concept", ConceptOrigin.USER, "3.80", idea.id),
        ("Market-derived seasonal concept", ConceptOrigin.MARKET, "3.20", None),
        ("Owner's concept, repositioned", ConceptOrigin.HYBRID, "4.00", idea.id),
    ]:
        await uow.concepts.add(
            _concept(
                workflow,
                title=title,
                origin=origin,
                differentiation=f"Placeholder differentiator for {origin.value} origin",
                score=score,
                original_idea_id=linked,
                research_run_id=run.id,
            )
        )

    for to_state, reason in [
        (RunStatus.RESEARCH_QUEUED, "research_enqueued"),
        (RunStatus.RESEARCHING, "research_started"),
        (RunStatus.IDEA_REVIEW, "research_completed"),
    ]:
        await uow.workflows.transition(
            workflow,
            to_state=to_state,
            expected_version=workflow.version,
            reason=reason,
            actor="fixture",
        )

    # Rejected first. The rejection stays in the history forever.
    await _decide(
        uow,
        workflow,
        gate=ApprovalGate.IDEA_APPROVAL,
        decision=ApprovalDecision.REJECTED,
        target_type="ProductWorkflow",
        target_id=workflow.id,
        target_version=workflow.version,
        comment="None of these carry the muddy-boots angle I asked for.",
    )

    # Back through research, then approved on the second pass.
    for to_state, reason in [
        (RunStatus.RESEARCH_QUEUED, "research_re_enqueued"),
        (RunStatus.RESEARCHING, "research_started"),
        (RunStatus.IDEA_REVIEW, "research_completed"),
    ]:
        await uow.workflows.transition(
            workflow,
            to_state=to_state,
            expected_version=workflow.version,
            reason=reason,
            actor="fixture",
        )
    await _decide(
        uow,
        workflow,
        gate=ApprovalGate.IDEA_APPROVAL,
        decision=ApprovalDecision.APPROVED,
        target_type="ProductWorkflow",
        target_id=workflow.id,
        target_version=workflow.version,
        comment="The repositioned version works.",
    )
    return workflow


async def _decide(
    uow: UnitOfWork,
    workflow: ProductWorkflow,
    *,
    gate: ApprovalGate,
    decision: ApprovalDecision,
    target_type: str,
    target_id: uuid.UUID,
    target_version: int,
    comment: str,
) -> None:
    """Record a gate decision and move the workflow, as the use case would."""
    from app.domain.workflow import apply_approval

    previous_state = workflow.state
    resulting_state = apply_approval(previous_state, gate, decision=decision)

    approval = await uow.approvals.record(
        workflow=workflow,
        gate=gate,
        decision=decision,
        previous_state=previous_state,
        resulting_state=resulting_state,
        actor="fixture",
        target_type=target_type,
        target_id=target_id,
        target_version=target_version,
        comment=comment,
    )
    if resulting_state is not previous_state:
        await uow.workflows.transition(
            workflow,
            to_state=resulting_state,
            expected_version=workflow.version,
            reason=f"approval:{gate.value}:{decision.value}",
            actor="fixture",
            gate=gate,
            decision=decision,
        )
    await uow.audit.record(
        action=AuditAction.APPROVAL_DECISION,
        entity_type="Approval",
        entity_id=approval.id,
        approval_id=approval.id,
        workflow_id=workflow.id,
        actor="fixture",
        summary=f"{DEV_DATA_MARKER} {gate} decided {decision}",
    )


async def seed_development_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, uuid.UUID]:
    """Create the three fixture workflows. Idempotent.

    Returns the fixed IDs so a caller can look them up without guessing.
    """
    async with UnitOfWork(session_factory) as uow:
        owner = await _seed_owner(uow)

        existing = await uow.workflows.get(FIXTURE_IDS["workflow_market_led"])
        if existing is not None:
            # Already seeded. Re-running must not duplicate the history.
            return FIXTURE_IDS

        await _seed_market_led(uow, owner)
        await _seed_user_idea(uow, owner)
        await _seed_hybrid(uow, owner)
        await uow.commit()

    return FIXTURE_IDS


async def _main() -> None:
    settings: Settings = get_settings()
    if settings.app_env != "local":
        raise SystemExit(
            f"Refusing to seed development fixtures with APP_ENV={settings.app_env}. "
            "This data is not real and must never reach staging or production."
        )

    engine = create_engine(settings.database_url)
    try:
        ids = await seed_development_data(create_session_factory(engine))
        for name, value in ids.items():
            print(f"{name}: {value}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
