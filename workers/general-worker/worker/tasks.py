from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import dramatiq
import httpx
from dramatiq.middleware import CurrentMessage
from sqlalchemy import select

from app.api.dependencies import build_credential_cipher
from app.application.artwork import ensure_artwork_within_budget, estimate_artwork_cost
from app.application.owner_settings import reveal_credential
from app.application.research import ensure_research_within_budget
from app.application.telegram import send_telegram_notification
from app.application.unit_of_work import UnitOfWork
from app.domain import ip_risk
from app.domain.enums import (
    AuditAction,
    CompetitionLevel,
    ConceptOrigin,
    ConceptStatus,
    ConfidenceLevel,
    IdeaMode,
    ProviderName,
    Seasonality,
    SourceType,
)
from app.domain.errors import BudgetExceededError
from app.domain.money import Money
from app.domain.workflow import (
    FailureStatus,
    JobStatus,
    RiskLevel,
    RunStatus,
)
from app.infrastructure.database import create_engine, create_session_factory
from app.infrastructure.logging import get_logger
from app.infrastructure.mockup_catalog import get_requested_mockup_products
from app.infrastructure.models import (
    Asset,
    DesignPrompt,
    KeywordCluster,
    ProductConcept,
    ProviderCredential,
    ResearchEvidence,
)
from app.infrastructure.models.audit import WorkflowFailure
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    ImageGenerationProvider,
    ImageRequest,
    ResearchProvider,
    SearchQuery,
    SearchResult,
    TextGenerationProvider,
    TextRequest,
)

# Providers
from app.ports.telegram import TelegramGateway
from app.providers.fake import FakeImageProvider, FakeResearchProvider, FakeTextProvider
from app.providers.gemini import GeminiImageAdapter, GeminiSynthesisAdapter
from app.providers.recraft import RecraftImageAdapter
from app.providers.s3 import S3ObjectStorage
from app.providers.search import TavilySearchAdapter
from app.providers.telegram import (
    FakeTelegramGateway,
    RealTelegramGateway,
    escape_html,
)
from app.settings import get_settings
from worker.retry import retry_after, should_retry

logger = get_logger("worker.tasks")


@dramatiq.actor(max_retries=3, queue_name="default")
def run_research_task(workflow_id: str, run_id: str) -> None:
    """Synchronous Dramatiq actor entrypoint.

    Spawns the async runner block.
    """
    logger.info("research_task_triggered", workflow_id=workflow_id, run_id=run_id)
    try:
        asyncio.run(_run_research_async(uuid.UUID(workflow_id), uuid.UUID(run_id)))
    except dramatiq.errors.Retry:
        # Re-raise Dramatiq Retry exception so the framework handles it
        raise
    except ProviderError as exc:
        message = CurrentMessage.get_current_message()
        attempt = (message.options.get("retries", 0) if message else 0) + 1

        # ``should_retry`` is the single policy every actor shares: a permanent
        # 4xx, a missing credential or an exhausted budget never comes back,
        # and neither does an attempt past the cap.
        if not should_retry(exc, attempt):
            logger.error(
                "research_task_permanent_provider_error",
                kind=exc.kind,
                attempt=attempt,
                message=exc.message,
            )
            asyncio.run(_mark_failure_async(uuid.UUID(workflow_id), uuid.UUID(run_id), exc.message))
            return

        delay_ms = int(retry_after(exc, attempt) * 1000)
        logger.info(
            "research_task_retry_scheduled",
            delay_ms=delay_ms,
            attempt=attempt,
            message=exc.message,
        )
        # Release the run before the redelivery arrives. The RUNNING guard in
        # the runner exists to drop duplicate deliveries of a live attempt; this
        # attempt is over, so leaving it RUNNING would make the runner skip its
        # own retry and strand the workflow in RESEARCHING forever.
        asyncio.run(_release_for_retry_async(uuid.UUID(run_id), exc.message))
        raise dramatiq.errors.Retry(delay=delay_ms) from exc
    except Exception as exc:
        logger.exception("research_task_unhandled_failure", error=str(exc))
        asyncio.run(_mark_failure_async(uuid.UUID(workflow_id), uuid.UUID(run_id), str(exc)))
        # Re-raised after the run is marked failed so an unclassified bug still
        # reaches Dramatiq's dead letter queue instead of vanishing.
        raise


async def _release_for_retry_async(run_id: uuid.UUID, reason: str) -> None:
    """Put a failed attempt's run back in the queue so the retry may claim it.

    The workflow stays in RESEARCHING: the research is still in flight as far as
    the owner is concerned, and the runner tolerates re-entering that state.
    """
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with UnitOfWork(session_factory) as uow:
            run = await uow.research.get_run(run_id)
            if run is None:
                return
            await uow.research.update_run(run_id, status=JobStatus.QUEUED, failure_reason=reason)
            await uow.commit()
    except Exception as exc:
        # A failure here only costs the retry, which Dramatiq will still deliver
        # and the runner will then skip; it must not mask the provider error.
        logger.exception("failed_to_release_run_for_retry", error=str(exc))
    finally:
        await engine.dispose()


async def _mark_failure_async(workflow_id: uuid.UUID, run_id: uuid.UUID, reason: str) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with UnitOfWork(session_factory) as uow:
            run = await uow.research.get_run(run_id)
            if run:
                await uow.research.update_run(
                    run_id,
                    status=JobStatus.FAILED,
                    completed_at=datetime.now(UTC),
                    failure_reason=reason,
                )
            # Add a WorkflowFailure record
            is_transient = "timeout" in reason.lower() or "http" in reason.lower()
            failure = WorkflowFailure(
                workflow_id=workflow_id,
                failure_state=FailureStatus.RESEARCH_FAILED.value,
                stage="research",
                error_kind="transient" if is_transient else "permanent",
                error_message=reason,
                attempt=1,
                retryable=True,
            )
            session = uow._session
            assert session is not None
            session.add(failure)

            await uow.audit.record(
                action=AuditAction.FAILURE_RECORDED,
                entity_type="ResearchRun",
                entity_id=run_id,
                workflow_id=workflow_id,
                actor="system",
                summary=f"Research failed: {reason[:150]}",
            )
            await uow.commit()
    except Exception as e:
        logger.exception("failed_to_mark_failure", error=str(e))
    finally:
        await engine.dispose()


async def _run_research_async(workflow_id: uuid.UUID, run_id: uuid.UUID) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    try:
        async with UnitOfWork(session_factory) as uow:
            # 1. Load run and workflow
            run = await uow.research.get_run(run_id)
            if not run:
                logger.error("research_run_not_found", run_id=str(run_id))
                return

            # Delivery is at least once: a redelivered message must not run the
            # paid work a second time.
            if run.status in {JobStatus.RUNNING, JobStatus.SUCCEEDED, JobStatus.FAILED}:
                logger.info(
                    "research_run_already_processed",
                    run_id=str(run_id),
                    status=run.status.value,
                )
                return

            workflow = await uow.workflows.get(workflow_id)
            if not workflow:
                logger.error("workflow_not_found", workflow_id=str(workflow_id))
                return

            # The API checked this before queueing, but the ledger can move
            # between then and delivery, so the wallet is protected here.
            try:
                await ensure_research_within_budget(
                    uow,
                    owner_id=workflow.owner_id,
                    provider_mode=settings.provider_mode,
                )
            except BudgetExceededError as exc:
                # Budget is never retryable: waiting does not make it cheaper.
                raise ProviderError(
                    kind=ProviderErrorKind.BUDGET_EXCEEDED,
                    provider="system",
                    operation="budget_check",
                    message=str(exc),
                ) from exc

            # Update status to RESEARCHING
            await uow.research.update_run(
                run_id, status=JobStatus.RUNNING, started_at=datetime.now(UTC)
            )
            # A retried attempt finds the workflow already RESEARCHING; the
            # state machine has no self-loop, so only the first attempt moves it.
            if workflow.state is not RunStatus.RESEARCHING:
                await uow.workflows.transition(
                    workflow,
                    to_state=RunStatus.RESEARCHING,
                    expected_version=workflow.version,
                    reason="Research runner started",
                    actor="system",
                )
            await uow.commit()

        # Reload settings and credentials in a separate UOW/DB block
        async with UnitOfWork(session_factory) as uow:
            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None

            owner_settings = await uow.owner_settings.get_for_user(workflow.owner_id)
            if not owner_settings:
                owner_settings = await uow.owner_settings.create_defaults(workflow.owner_id)
                await uow.commit()

            gemini_api_key: str | None = None
            tavily_api_key: str | None = None

            if settings.provider_mode == "live":
                cipher = build_credential_cipher(settings)
                if not cipher:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider="system",
                        operation="build_credential_cipher",
                        message="Encryption cipher could not be initialized. Check ENCRYPTION_KEY.",
                    )
                try:
                    gemini_api_key = await reveal_credential(
                        uow,
                        workflow.owner_id,
                        provider=ProviderName.GEMINI,
                        cipher=cipher,
                    )
                except Exception as exc:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider="gemini",
                        operation="resolve_credential",
                        message="Gemini API Key is missing or invalid in credentials.",
                    ) from exc

                if settings.tavily_api_key:
                    tavily_api_key = settings.tavily_api_key.get_secret_value()
                else:
                    try:
                        tavily_cred = await uow.credentials.get(
                            workflow.owner_id, ProviderName.TAVILY
                        )
                        if tavily_cred:
                            tavily_api_key = cipher.decrypt(
                                tavily_cred.ciphertext, key_version=tavily_cred.key_version
                            )
                    except Exception:
                        logger.debug("no_tavily_cred_stored")

                if not tavily_api_key:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider="tavily",
                        operation="resolve_credential",
                        message="Tavily API Key is missing. Set TAVILY_API_KEY env var.",
                    )

        # 2. Query Research API (Tavily or Fake)
        brief_theme = workflow.name
        user_idea_text = ""
        idea_slogan = ""
        idea_style = ""
        idea_season = ""
        idea_buyer = ""

        async with UnitOfWork(session_factory) as uow:
            original_idea = await uow.ideas.get_for_workflow(workflow_id)
            if original_idea:
                user_idea_text = original_idea.original_text
                idea_slogan = original_idea.slogan or ""
                idea_style = original_idea.desired_style or ""
                idea_season = original_idea.season or ""
                idea_buyer = original_idea.audience or ""

        target_theme = user_idea_text or brief_theme
        search_theme = target_theme
        if workflow.idea_mode == IdeaMode.MARKET_LED:
            import re

            match = re.search(r"\(([^)]+)\)", target_theme)
            if match:
                search_theme = match.group(1)
            elif "Trend Discovery" in target_theme:
                search_theme = "trending design trends"

        angles = {
            "broad": f"{search_theme} png design clipart",
            "long-tail": f"hand-drawn {search_theme} sublimation transparent background",
            "recipient": f"{idea_buyer or 'gift'} {search_theme} png",
            "style": f"{idea_style or 'retro groovy'} {search_theme} clipart",
            "use-case": f"{search_theme} sublimation design for mug shirt",
        }

        search_provider: ResearchProvider
        if settings.provider_mode == "live" and tavily_api_key:
            search_provider = TavilySearchAdapter(api_key=tavily_api_key)
        else:
            search_provider = FakeResearchProvider()

        evidence_list: list[tuple[str, str, SearchResult]] = []
        query_angles_run: list[str] = []

        for angle_name, query_text in angles.items():
            query_angles_run.append(angle_name)
            logger.info("running_search_query", angle=angle_name, query=query_text)
            try:
                results = await search_provider.search(
                    SearchQuery(text=query_text, angle=angle_name)
                )
                for res in results:
                    evidence_list.append((angle_name, query_text, res))
            except Exception as e:
                logger.warning(
                    "search_query_failed", angle=angle_name, query=query_text, error=str(e)
                )

        if not evidence_list:
            raise RuntimeError("No search evidence could be aggregated from search provider.")

        # 3. Synthesize Findings using Text Provider (Gemini or Fake)
        text_provider: TextGenerationProvider
        if settings.provider_mode == "live" and gemini_api_key:
            text_provider = GeminiSynthesisAdapter(api_key=gemini_api_key)
        else:
            text_provider = FakeTextProvider()

        evidence_content = "\n".join(
            [
                f"Angle: {angle} | Title: {item.title} | Source: {item.url}\n"
                f"Observation: {item.observation}"
                for angle, _, item in evidence_list
            ]
        )

        system_prompt = (
            "You are an expert market analyst and creative prompt engineer "
            "for Etsy print-on-demand sellers.\n"
            "Your job is to synthesize web research evidence about digital PNG "
            "product opportunities and produce exactly 3 unique, ranked product concepts.\n"
            "You must output a JSON object following this JSON schema exactly:\n"
            "{\n"
            '  "confidence": "high" | "medium" | "low",\n'
            '  "proposed_test": "string outlining how to test if confidence is low",\n'
            '  "keyword_clusters": [\n'
            "    {\n"
            '      "primary_phrase": "string",\n'
            '      "attributes": ["string"],\n'
            '      "recipient_occasion_terms": ["string"],\n'
            '      "use_case_terms": ["string"],\n'
            '      "competition_level": "saturated" | "crowded" | '
            '"differentiable" | "thin",\n'
            '      "competition_note": "string detailing why this level was selected",\n'
            '      "relevance_rank": int (0 to 100)\n'
            "    }\n"
            "  ],\n"
            '  "concepts": [\n'
            "    {\n"
            '      "title": "string",\n'
            '      "description": "string",\n'
            '      "differentiation": "string stating plain differentiator (do not say '
            "'same but prettier')\",\n"
            '      "target_buyer": "string",\n'
            '      "buyer_use_case": "string",\n'
            '      "seasonality": "evergreen" | "seasonal" | "both",\n'
            '      "risk_level": "low" | "medium" | "high",\n'
            '      "risk_note": "string detailed brand/IP trademark warnings",\n'
            '      "score_breakdown": {\n'
            '        "demand": int (1 to 5),\n'
            '        "competition_opportunity": int (1 to 5),\n'
            '        "seasonal_timing": int (1 to 5),\n'
            '        "buyer_clarity": int (1 to 5),\n'
            '        "differentiation": int (1 to 5),\n'
            '        "product_versatility": int (1 to 5),\n'
            '        "ip_safety": int (1 to 5)\n'
            "      },\n"
            '      "score_explanation": "string summary of how the scores compare",\n'
            '      "fidelity": "High" | "Medium" | "Low",\n'
            '      "origin": "user" | "market" | "hybrid",\n'
            '      "prompt": {\n'
            '        "positive_prompt": "string detailing central subject, style, '
            'composition, details, palette, isolated artwork on a transparent background",\n'
            '        "negative_prompt": "string detailing elements to reject '
            '(background, mockups, watermarks, etc.)",\n'
            '        "typography_instructions": "string or null detailing font, layout, '
            'placement",\n'
            '        "exact_slogan": "string or null detailing exact text slogans",\n'
            '        "intended_product_uses": ["string"],\n'
            '        "style_notes": "string or null",\n'
            '        "palette": "string or null",\n'
            '        "post_generation_checklist": ["string"],\n'
            '        "generation_metadata": {}\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "\n"
            "Rules to strictly follow:\n"
            "1. For 'user-idea' mode: You MUST generate EXACTLY ONE concept. "
            "It must be a faithful, improved, and analyzed version of the user's provided idea. "
            "If the user provided an exact slogan, you MUST preserve it verbatim in the "
            "'exact_slogan' field of this concept, unless risk/trademark checks reject/flag it. "
            "Set fidelity to 'High' and origin to 'user'.\n"
            "2. For 'hybrid' mode: You MUST generate EXACTLY 3 concepts, which MUST be derived "
            "variations of the user's theme/direction and remain recognizably connected to it, "
            "while informing them with market research. "
            "Set origin to 'hybrid' and fidelity to 'Medium'.\n"
            "3. For 'market-led' mode: You MUST generate EXACTLY 3 concepts, discovering "
            "opportunities from the market/seasonal research evidence. "
            "Set origin to 'market' and fidelity to 'Low'.\n"
            "4. Never name living artists in the positive prompt. Style must be descriptive "
            "(e.g. textured watercolor shading, vintage retro groovy style).\n"
            "5. Every prompt must demand 'isolated central artwork on a transparent background' "
            "and 'clean uncropped edges'.\n"
            "6. Keep typography separate. Slogans should be null in the positive prompt, and exact "
            "phrases must be listed in exact_slogan and layout instructions in "
            "typography_instructions.\n"
            "7. Never invent or include fake search volume numbers."
        )

        user_prompt = (
            f"Here is the research brief and aggregated web trends evidence:\n"
            f"Marketplace: {workflow.target_marketplace}\n"
            f"Country / Language: {workflow.target_country} / {workflow.output_language}\n"
            f"Buyer Category: {workflow.target_buyer or 'Not specified'}\n"
            f"Intended Physical Uses: {', '.join(workflow.intended_product_uses)}\n"
            f"Idea Input Mode: {workflow.idea_mode.value}\n"
        )
        if user_idea_text:
            user_prompt += (
                f"Original User Idea / Theme Direction: {user_idea_text}\n"
                f"User Style Direction: {idea_style}\n"
                f"User Season: {idea_season}\n"
            )
            if idea_slogan:
                user_prompt += (
                    f"User Slogan: {idea_slogan} (Preserve verbatim unless "
                    "it fails trademark/IP validation)\n"
                )
            else:
                user_prompt += (
                    "User Slogan: None provided (You may suggest a slogan if appropriate)\n"
                )
        user_prompt += f"\nSearch Evidence Collected:\n{evidence_content}\n"

        # Record estimate in ledger before paid call
        estimated_price = Money(1, "USD")
        is_live = settings.provider_mode == "live"
        async with UnitOfWork(session_factory) as uow:
            ledger_entry = await uow.costs.record_estimate(
                workflow_id=workflow_id,
                provider=ProviderName.GEMINI if is_live else ProviderName.FAKE,
                service="synthesis",
                operation="research_synthesis",
                estimated=estimated_price,
                input_units=len(user_prompt.split()),
                output_units=500,
                unit_kind="tokens",
                idempotency_key=f"cost-research-synthesis-{run_id}",
            )
            await uow.commit()

        logger.info("running_gemini_structured_synthesis")
        text_response = await text_provider.generate(
            TextRequest(prompt=user_prompt, system=system_prompt, max_output_tokens=8192)
        )

        # Parse synthesized payload
        synthesis = json.loads(text_response.text)

        # 4. Save results to the database in a transaction
        async with UnitOfWork(session_factory) as uow:
            db_run = await uow.research.get_run(run_id)
            assert db_run is not None
            db_workflow = await uow.workflows.get(workflow_id)
            assert db_workflow is not None

            # Save query angles and status on run
            db_run.query_angles = query_angles_run
            db_run.confidence = ConfidenceLevel(synthesis.get("confidence", "low").lower())
            db_run.proposed_test = synthesis.get("proposed_test")

            # Save Evidence
            for angle_name, query_text, item in evidence_list:
                db_evidence = ResearchEvidence(
                    run_id=run_id,
                    search_query=query_text,
                    query_angle=angle_name,
                    source_url=item.url,
                    source_title=item.title,
                    source_type=SourceType.FAKE if not is_live else SourceType.TRENDS,
                    observation=item.observation,
                    observed_at=item.captured_at,
                    market=workflow.target_country,
                    language=workflow.output_language,
                )
                await uow.research.add_evidence(db_evidence)

            # Save Keyword Clusters
            for cluster_data in synthesis.get("keyword_clusters", []):
                comp_level = CompetitionLevel(
                    cluster_data.get("competition_level", "unknown").lower()
                )
                db_cluster = KeywordCluster(
                    run_id=run_id,
                    primary_phrase=cluster_data["primary_phrase"],
                    attributes=cluster_data.get("attributes", []),
                    recipient_occasion_terms=cluster_data.get("recipient_occasion_terms", []),
                    use_case_terms=cluster_data.get("use_case_terms", []),
                    market=workflow.target_country,
                    language=workflow.output_language,
                    competition_level=comp_level,
                    competition_note=cluster_data.get("competition_note"),
                    relevance_rank=cluster_data.get("relevance_rank", 50),
                )
                await uow.research.add_keyword_cluster(db_cluster)

            # Save Product Concepts and Prompts
            original_idea_record = await uow.ideas.get_for_workflow(workflow_id)
            original_idea_id = original_idea_record.id if original_idea_record else None

            for index, concept_data in enumerate(synthesis.get("concepts", [])):
                score_breakdown = concept_data.get("score_breakdown", {})

                weighted_score = (
                    0.20 * score_breakdown.get("demand", 3)
                    + 0.15 * score_breakdown.get("competition_opportunity", 3)
                    + 0.15 * score_breakdown.get("seasonal_timing", 3)
                    + 0.15 * score_breakdown.get("buyer_clarity", 3)
                    + 0.15 * score_breakdown.get("differentiation", 3)
                    + 0.10 * score_breakdown.get("product_versatility", 3)
                    + 0.10 * score_breakdown.get("ip_safety", 3)
                )

                origin_str = concept_data.get("origin", "market").lower()
                origin = ConceptOrigin(origin_str)

                risk_level_str = concept_data.get("risk_level", "low").lower()
                risk_note = concept_data.get("risk_note", "")

                # The model self-reports a risk level; the screen can only make
                # it worse, never better, so a model that says "low" about a
                # flagged phrase cannot talk its way past the gate.
                flagged = ip_risk.scan(
                    concept_data["title"],
                    concept_data["description"],
                    concept_data.get("prompt", {}).get("exact_slogan"),
                )
                if flagged:
                    risk_level_str = "high"
                    risk_note = f"Trademark brand names flagged: {', '.join(flagged)}. {risk_note}"

                db_concept = ProductConcept(
                    workflow_id=workflow_id,
                    original_idea_id=(
                        original_idea_id
                        if origin in [ConceptOrigin.USER, ConceptOrigin.HYBRID]
                        else None
                    ),
                    research_run_id=run_id,
                    title=concept_data["title"],
                    description=concept_data["description"],
                    origin=origin,
                    differentiation=concept_data["differentiation"],
                    target_buyer=concept_data.get("target_buyer"),
                    buyer_use_case=concept_data.get("buyer_use_case"),
                    seasonality=Seasonality(concept_data.get("seasonality", "evergreen").lower()),
                    risk_level=RiskLevel(risk_level_str),
                    risk_note=risk_note,
                    score=weighted_score,
                    score_breakdown=score_breakdown,
                    score_explanation=concept_data.get("score_explanation"),
                    status=ConceptStatus.PROPOSED if index > 0 else ConceptStatus.SHORTLISTED,
                )
                await uow.concepts.add(db_concept)

                # Save Prompt Version 1
                prompt_data = concept_data["prompt"]
                await uow.concepts.add_prompt_version(
                    db_concept,
                    positive_prompt=prompt_data["positive_prompt"],
                    negative_prompt=prompt_data["negative_prompt"],
                    typography_instructions=prompt_data.get("typography_instructions"),
                    exact_slogan=prompt_data.get("exact_slogan"),
                    change_note="Initial prompt generation.",
                    intended_product_uses=prompt_data.get("intended_product_uses", []),
                    style_notes=prompt_data.get("style_notes"),
                    palette=prompt_data.get("palette"),
                    post_generation_checklist=prompt_data.get("post_generation_checklist", []),
                    generation_metadata=prompt_data.get("generation_metadata", {}),
                )

            # Reconcile usage costs
            tokens_in = text_response.input_tokens
            tokens_out = text_response.output_tokens
            cost_in = Money(int(tokens_in * 0.0075), "USD") if is_live else Money(0, "USD")
            cost_out = Money(int(tokens_out * 0.030), "USD") if is_live else Money(0, "USD")
            actual_cost = Money(cost_in.minor_units + cost_out.minor_units, "USD")

            await uow.costs.reconcile(
                usage_id=ledger_entry.id,
                actual=actual_cost,
                input_units=tokens_in,
                output_units=tokens_out,
            )

            # Complete the research run
            await uow.research.update_run(
                run_id,
                status=JobStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
            )

            # Transition workflow to IDEA_REVIEW
            await uow.workflows.transition(
                db_workflow,
                to_state=RunStatus.IDEA_REVIEW,
                expected_version=db_workflow.version,
                reason="Research synthesis complete. Waiting for Gate 1 human approval.",
                actor="system",
            )

            # Record final audit event
            audit_after: dict[str, object] = {
                "status": JobStatus.SUCCEEDED.value,
                "workflow_state": RunStatus.IDEA_REVIEW.value,
            }
            await uow.audit.record(
                action=AuditAction.JOB_STATUS_CHANGED,
                entity_type="ResearchRun",
                entity_id=run_id,
                workflow_id=workflow_id,
                actor="system",
                summary="Research job completed successfully.",
                after=audit_after,
            )

            await uow.commit()

    except Exception as exc:
        logger.exception("research_execution_failed", error=str(exc))
        raise exc
    finally:
        await engine.dispose()


@dramatiq.actor(max_retries=3, queue_name="default")
def run_artwork_task(workflow_id: str, job_id: str) -> None:
    """Synchronous Dramatiq actor entrypoint for artwork generation.

    Spawns the async runner block.
    """
    logger.info("artwork_task_triggered", workflow_id=workflow_id, job_id=job_id)
    try:
        asyncio.run(_run_artwork_async(uuid.UUID(workflow_id), uuid.UUID(job_id)))
    except dramatiq.errors.Retry:
        raise
    except ProviderError as exc:
        message = CurrentMessage.get_current_message()
        attempt = (message.options.get("retries", 0) if message else 0) + 1

        if not should_retry(exc, attempt):
            logger.error(
                "artwork_task_permanent_provider_error",
                kind=exc.kind,
                attempt=attempt,
                message=exc.message,
            )
            asyncio.run(
                _mark_artwork_failure_async(uuid.UUID(workflow_id), uuid.UUID(job_id), exc.message)
            )
            return

        delay_ms = int(retry_after(exc, attempt) * 1000)
        logger.info(
            "artwork_task_retry_scheduled",
            delay_ms=delay_ms,
            attempt=attempt,
            message=exc.message,
        )
        raise dramatiq.errors.Retry(delay=delay_ms) from exc
    except Exception as exc:
        logger.exception("artwork_task_unhandled_failure", error=str(exc))
        asyncio.run(
            _mark_artwork_failure_async(uuid.UUID(workflow_id), uuid.UUID(job_id), str(exc))
        )
        raise


async def _mark_artwork_failure_async(
    workflow_id: uuid.UUID, job_id: uuid.UUID, reason: str
) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with UnitOfWork(session_factory) as uow:
            job = await uow.artwork_jobs.get(job_id)
            if job is not None:
                await uow.artwork_jobs.update(
                    job_id,
                    status=JobStatus.FAILED,
                    completed_at=datetime.now(UTC),
                    failure_kind="generation_failure",
                    failure_message=reason,
                )

            # Record a WorkflowFailure record
            is_transient = "timeout" in reason.lower() or "http" in reason.lower()
            failure = WorkflowFailure(
                workflow_id=workflow_id,
                failure_state="ART_GENERATION_FAILED",
                stage="artwork",
                error_kind="transient" if is_transient else "permanent",
                error_message=reason,
                attempt=1,
                retryable=True,
            )
            session = uow._session
            assert session is not None
            session.add(failure)

            await uow.audit.record(
                action=AuditAction.FAILURE_RECORDED,
                entity_type="ArtworkJob",
                entity_id=job_id,
                workflow_id=workflow_id,
                actor="system",
                summary=f"Artwork failed: {reason[:150]}",
            )
            await uow.commit()
    except Exception as e:
        logger.exception("failed_to_mark_artwork_failure", error=str(e))
    finally:
        await engine.dispose()


async def _run_artwork_async(workflow_id: uuid.UUID, job_id: uuid.UUID) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    cipher = build_credential_cipher(settings)

    try:
        # 1. Load job and workflow details
        async with UnitOfWork(session_factory) as uow:
            job = await uow.artwork_jobs.get(job_id)
            if job is None or job.workflow_id != workflow_id:
                raise ValueError("ArtworkJob not found")

            workflow = await uow.workflows.get(workflow_id)
            if workflow is None:
                raise ValueError("Workflow not found")

            assert uow._session is not None
            prompt = await uow._session.get(DesignPrompt, job.prompt_id)
            if prompt is None:
                raise ValueError("DesignPrompt not found")

            # Copy parameters to narrow types/local variables to satisfy the type checker
            job_provider = job.provider
            job_provider_model = job.provider_model
            job_requested_width = job.requested_width
            job_requested_height = job.requested_height
            job_quality = job.quality
            job_idempotency_key = job.idempotency_key
            workflow_owner_id = workflow.owner_id
            workflow_version = workflow.version
            workflow_name = workflow.name
            prompt_positive_prompt = prompt.positive_prompt
            prompt_negative_prompt = prompt.negative_prompt
            prompt_generation_metadata = prompt.generation_metadata

        # 2. Update job status to RUNNING and bump attempt count
        async with UnitOfWork(session_factory) as uow:
            job = await uow.artwork_jobs.get(job_id)
            assert job is not None
            job.status = JobStatus.RUNNING
            job.attempt_count += 1
            job.started_at = datetime.now(UTC)

            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None
            if workflow.state == RunStatus.ART_QUEUED:
                await uow.workflows.transition(
                    workflow,
                    to_state=RunStatus.ART_GENERATION,
                    expected_version=workflow.version,
                    reason="Artwork generation started",
                    actor="system",
                )
            elif workflow.state != RunStatus.ART_GENERATION:
                try:
                    await uow.workflows.transition(
                        workflow,
                        to_state=RunStatus.ART_GENERATION,
                        expected_version=workflow.version,
                        reason="Artwork generation started",
                        actor="system",
                    )
                except Exception as trans_err:
                    logger.warning("Could not transition workflow to ART_GENERATION: %s", trans_err)
            await uow.commit()

        # 3. Initialize S3 storage
        storage = S3ObjectStorage(
            endpoint_url=settings.s3_endpoint_url,
            bucket_name=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            region_name=settings.s3_region,
            force_path_style=settings.s3_force_path_style,
        )

        # 4. Resolve credentials, check budget & reference images
        is_live = settings.provider_mode == "live"
        provider_key = None
        ref_image_bytes = None
        ref_image_mime = None
        # Check reference image / refinement
        is_refinement = False
        if prompt_generation_metadata is not None and prompt_generation_metadata.get(
            "reference_asset_id"
        ):
            is_refinement = True

        if is_refinement:
            candidate_count = 2
        elif "pro" in (job_provider_model or "").lower():
            candidate_count = 1
        else:
            candidate_count = 4

        async with UnitOfWork(session_factory) as uow:
            # Check reference image
            if prompt_generation_metadata is not None:
                ref_asset_id_str = prompt_generation_metadata.get("reference_asset_id")
                if ref_asset_id_str:
                    ref_asset = await uow.assets.get(uuid.UUID(str(ref_asset_id_str)))
                    if ref_asset is not None:
                        ref_image_bytes = await storage.get(ref_asset.storage_key)
                        ref_image_mime = ref_asset.mime_type

            # Check budget limit
            owner_settings = await ensure_artwork_within_budget(
                uow,
                owner_id=workflow_owner_id,
                provider=job_provider.value,
                model=job_provider_model,
                candidate_count=candidate_count,
                provider_mode=settings.provider_mode,
            )
            currency = owner_settings.currency

            if is_live:
                if not cipher:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider=job_provider.value,
                        operation="reveal_credential",
                        message="Encryption cipher could not be initialized. Check ENCRYPTION_KEY.",
                    )
                try:
                    provider_key = await reveal_credential(
                        uow, workflow_owner_id, provider=job_provider, cipher=cipher
                    )
                except Exception as exc:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider=job_provider.value,
                        operation="reveal_credential",
                        message=(
                            f"{job_provider.value} API Key is missing or invalid in credentials."
                        ),
                    ) from exc

        # 5. Record cost estimate in ledger before paid call
        estimated_price = estimate_artwork_cost(
            provider=job_provider.value,
            model=job_provider_model,
            candidate_count=candidate_count,
            currency=currency,
            provider_mode=settings.provider_mode,
        )

        async with UnitOfWork(session_factory) as uow:
            ledger_entry = await uow.costs.record_estimate(
                workflow_id=workflow_id,
                provider=job_provider,
                service="artwork",
                operation="generate_image",
                estimated=estimated_price,
                input_units=1,
                output_units=candidate_count,
                unit_kind="images",
                idempotency_key=f"cost-artwork-{job_id}",
            )
            await uow.commit()

        # 6. Initialize provider adapter
        image_provider: ImageGenerationProvider | None = None
        fallback_provider = None
        if is_live and provider_key:
            if job_provider == ProviderName.RECRAFT:
                image_provider = RecraftImageAdapter(
                    api_key=provider_key, default_model=job_provider_model or "recraftv4_1"
                )
            elif job_provider == ProviderName.GEMINI:
                image_provider = GeminiImageAdapter(
                    api_key=provider_key,
                    default_model=job_provider_model or "gemini-3.1-flash-image",
                )

        if image_provider is None:
            image_provider = FakeImageProvider()

        # 7. Execute image generation (with fallback if refinement fails)
        request = ImageRequest(
            positive_prompt=prompt_positive_prompt,
            negative_prompt=prompt_negative_prompt or "",
            width=job_requested_width or 1024,
            height=job_requested_height or 1024,
            quality=job_quality or "standard",
            idempotency_key=job_idempotency_key,
            provider=job_provider.value,
            model=job_provider_model,
            aspect_ratio="1:1",
            transparent_background=True,
            candidate_count=candidate_count,
            reference_image_bytes=ref_image_bytes,
            reference_image_mime_type=ref_image_mime,
            strength=settings.recraft_refinement_strength if is_refinement else None,
        )

        response = None
        actual_provider = job_provider
        try:
            response = await image_provider.generate(request)
        except Exception as primary_err:
            # If refinement on Recraft fails and live mode is active, attempt Gemini fallback
            if is_refinement and is_live and job_provider == ProviderName.RECRAFT:
                logger.warning(
                    "Recraft refinement failed (%s). Attempting Gemini fallback...",
                    primary_err,
                )
                try:
                    async with UnitOfWork(session_factory) as uow:
                        gemini_key = await reveal_credential(
                            uow, workflow_owner_id, provider=ProviderName.GEMINI, cipher=cipher
                        )
                    if gemini_key:
                        fallback_provider = GeminiImageAdapter(
                            api_key=gemini_key,
                            default_model=settings.gemini_refinement_model,
                        )
                        gemini_req = ImageRequest(
                            positive_prompt=prompt_positive_prompt,
                            negative_prompt=prompt_negative_prompt or "",
                            width=job_requested_width or 1024,
                            height=job_requested_height or 1024,
                            quality=job_quality or "standard",
                            idempotency_key=f"{job_idempotency_key}-gemini-fallback",
                            provider=ProviderName.GEMINI.value,
                            model=settings.gemini_refinement_model,
                            aspect_ratio="1:1",
                            transparent_background=True,
                            candidate_count=candidate_count,
                            reference_image_bytes=ref_image_bytes,
                            reference_image_mime_type=ref_image_mime,
                            strength=settings.recraft_refinement_strength,
                        )
                        response = await fallback_provider.generate(gemini_req)
                        actual_provider = ProviderName.GEMINI
                except Exception as fallback_err:
                    logger.error("Gemini fallback also failed: %s", fallback_err)
                    raise primary_err from fallback_err

            if response is None:
                raise primary_err

        # 8. Clean candidates with local transparency pipeline, upload to S3, and record Assets
        candidate_assets: list[Asset] = []
        image_worker_url = settings.image_worker_url.rstrip("/")

        async with UnitOfWork(session_factory) as uow:
            job = await uow.artwork_jobs.get(job_id)
            assert job is not None
            workflow = await uow.workflows.get(workflow_id)
            assert workflow is not None

            for _idx, candidate in enumerate(response.candidates):
                cleaned_bytes = candidate.image_bytes
                cleaned_mime = candidate.mime_type

                # Run local edge-connected background cleanup for refinement outputs
                if is_refinement:
                    try:
                        async with httpx.AsyncClient(timeout=60.0) as http_client:
                            trans_res = await http_client.post(
                                f"{image_worker_url}/pipeline/ensure-transparency",
                                json={
                                    "image_base64": base64.b64encode(candidate.image_bytes).decode(
                                        "utf-8"
                                    ),
                                },
                            )
                            if trans_res.status_code == 200:
                                trans_data = trans_res.json()
                                cleaned_bytes = base64.b64decode(trans_data["image_base64"])
                                cleaned_mime = "image/png"
                    except Exception as clean_err:
                        logger.warning("Local transparency cleanup error: %s", clean_err)

                sha256 = hashlib.sha256(cleaned_bytes).hexdigest()

                existing_asset = await uow.assets.get_by_checksum_sha256(workflow_id, sha256)
                if existing_asset is not None:
                    candidate_assets.append(existing_asset)
                    continue

                ext = "svg" if cleaned_mime == "image/svg+xml" else "png"
                storage_key = f"assets/{workflow_id}/{uuid.uuid4()}.{ext}"

                stored_obj = await storage.put(storage_key, cleaned_bytes, cleaned_mime)

                derived_from_uuid = None
                if is_refinement and prompt_generation_metadata is not None:
                    ref_id_val = prompt_generation_metadata.get("reference_asset_id")
                    if ref_id_val:
                        derived_from_uuid = uuid.UUID(str(ref_id_val))

                provenance_data: dict[str, object] = {
                    "generator": actual_provider.value,
                    "model": response.model,
                    "prompt": prompt_positive_prompt,
                }
                if is_refinement:
                    provenance_data.update(
                        {
                            "operation": "refinement",
                            "provider": actual_provider.value,
                            "model": response.model,
                            "source_asset_id": str(derived_from_uuid)
                            if derived_from_uuid
                            else None,
                            "strength": settings.recraft_refinement_strength,
                            "change_note": prompt.change_note,
                            "background_cleanup": "local",
                        }
                    )

                new_asset = Asset(
                    id=uuid.uuid4(),
                    workflow_id=workflow_id,
                    artwork_job_id=job_id,
                    derived_from_id=derived_from_uuid,
                    storage_key=stored_obj.storage_key,
                    mime_type=stored_obj.content_type,
                    byte_size=stored_obj.byte_size,
                    checksum_sha256=stored_obj.sha256,
                    width=candidate.width or job_requested_width,
                    height=candidate.height or job_requested_height,
                    has_alpha=True,
                    has_transparent_pixels=True,
                    quality_check={},
                    provenance=provenance_data,
                )
                await uow.assets.add(new_asset)
                candidate_assets.append(new_asset)

            actual_cost = Money.from_decimal(response.cost_usd or Decimal("0.0"), currency)
            await uow.costs.reconcile(
                usage_id=ledger_entry.id,
                actual=actual_cost,
                input_units=1,
                output_units=len(response.candidates),
            )

            await uow.artwork_jobs.update(
                job_id,
                status=JobStatus.SUCCEEDED,
                completed_at=datetime.now(UTC),
                provider_job_id=response.provider_request_id,
            )

            if workflow.state != RunStatus.ART_REVIEW:
                await uow.workflows.transition(
                    workflow,
                    to_state=RunStatus.ART_REVIEW,
                    expected_version=workflow.version,
                    reason="Artwork generation succeeded. Waiting for Gate 2 human approval.",
                    actor="system",
                )

            await uow.audit.record(
                action=AuditAction.JOB_STATUS_CHANGED,
                entity_type="ArtworkJob",
                entity_id=job_id,
                workflow_id=workflow_id,
                actor="system",
                summary="Artwork generation succeeded.",
                after={
                    "status": JobStatus.SUCCEEDED.value,
                    "workflow_state": RunStatus.ART_REVIEW.value,
                },
            )
            await uow.commit()

        # 9. Send Telegram Notification
        try:
            inline_keyboard = []
            approve_row = []
            for idx, asset in enumerate(candidate_assets):
                approve_row.append(
                    {
                        "text": f"Approve {idx + 1}",
                        "callback_data": f"art_app:{asset.id}",
                    }
                )
            inline_keyboard.append(approve_row)

            inline_keyboard.append(
                [
                    {
                        "text": "Reject Options",
                        "callback_data": f"art_rej:{workflow_id}:{workflow_version}",
                    },
                    {"text": "Regenerate", "callback_data": f"art_reg:{workflow_id}"},
                ]
            )

            dash_origins = settings.cors_origins
            dash_base = dash_origins[0] if dash_origins else ""
            if (
                dash_base
                and not dash_base.startswith("http://localhost")
                and not dash_base.startswith("http://127.0.0.1")
            ):
                inline_keyboard.append(
                    [{"text": "Open Dashboard", "url": f"{dash_base}/workflow/{workflow_id}"}]
                )

            preview_links = []
            async with UnitOfWork(session_factory) as uow:
                for idx, asset in enumerate(candidate_assets):
                    signed_url = await storage.signed_url(asset.storage_key, 3600)
                    preview_links.append(
                        f'• <a href="{signed_url}">Candidate {idx + 1} Preview</a>'
                    )

            notify_text = (
                "🎨 <b>Artwork Generation Complete!</b>\n\n"
                f"Workflow: <b>{escape_html(workflow_name)}</b>\n"
                f"Provider: <code>{job_provider.value}</code>\n"
                f"Model: <code>{response.model}</code>\n"
                f"Cost: <b>{actual_cost.to_decimal():.4f} USD</b>\n\n"
                f"<b>Previews:</b>\n" + "\n".join(preview_links) + "\n\n"
                "Please review and approve a candidate below."
            )

            bot_token = None
            if settings.telegram_bot_token:
                bot_token = settings.telegram_bot_token.get_secret_value()
            elif settings.provider_mode == "live":
                try:
                    if cipher:
                        async with session_factory() as session:
                            stmt = (
                                select(ProviderCredential)
                                .where(ProviderCredential.provider == ProviderName.TELEGRAM)
                                .limit(1)
                            )
                            result = await session.execute(stmt)
                            cred = result.scalar_one_or_none()
                            if cred:
                                bot_token = cipher.decrypt(
                                    cred.ciphertext, key_version=cred.key_version
                                )
                except Exception as e:
                    logger.debug("bot_token_resolution_skipped", error=str(e))

            if settings.provider_mode == "live" and bot_token:
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    tg_gw: TelegramGateway = RealTelegramGateway(bot_token, http_client)
                    async with UnitOfWork(session_factory) as uow:
                        await send_telegram_notification(
                            uow,
                            tg_gw,
                            workflow_owner_id,
                            notify_text,
                            {"inline_keyboard": inline_keyboard},
                        )
            else:
                fake_gw: TelegramGateway = FakeTelegramGateway()
                async with UnitOfWork(session_factory) as uow:
                    await send_telegram_notification(
                        uow,
                        fake_gw,
                        workflow_owner_id,
                        notify_text,
                        {"inline_keyboard": inline_keyboard},
                    )

        except Exception as tg_exc:
            logger.warning("failed_to_send_telegram_notification", error=str(tg_exc))

    except Exception as exc:
        logger.exception("artwork_execution_failed", error=str(exc))
        raise exc
    finally:
        await engine.dispose()


def _normalize_mockup_products(raw_products: list[str] | None) -> list[str]:
    return get_requested_mockup_products(raw_products)


@dramatiq.actor(queue_name="production", max_retries=3)
def run_production_task(
    workflow_id: str, production_job_id: str | None = None, job_id: str | None = None
) -> None:
    """Entry point for Phase 7 PNG Production Pipeline."""
    actual_job_id = production_job_id or job_id
    assert actual_job_id is not None, "production_job_id or job_id is required"
    logger.info("production_task_triggered", workflow_id=workflow_id, job_id=actual_job_id)
    asyncio.run(_run_production_async(uuid.UUID(workflow_id), uuid.UUID(actual_job_id)))


async def _run_production_async(workflow_id: uuid.UUID, job_id: uuid.UUID) -> None:
    from worker.production import execute_production_pipeline

    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    try:
        await execute_production_pipeline(
            session_factory=session_factory,
            storage=storage,
            settings=settings,
            workflow_id=workflow_id,
            job_id=job_id,
            logger=logger,
        )
    except Exception as exc:
        logger.exception("production_execution_failed", error=str(exc))
        try:
            async with UnitOfWork(session_factory) as uow:
                job = await uow.production_jobs.get(job_id)
                if job:
                    await uow.production_jobs.update(
                        job_id,
                        status=JobStatus.FAILED,
                        failure_kind="PRODUCTION_ERROR",
                        failure_message=str(exc),
                        completed_at=datetime.now(UTC),
                    )

                failure_record = WorkflowFailure(
                    workflow_id=workflow_id,
                    failure_state=FailureStatus.PRODUCTION_FAILED.value,
                    stage="production",
                    error_kind="transient" if "timeout" in str(exc).lower() else "permanent",
                    error_message=str(exc),
                    attempt=1,
                    retryable=True,
                )
                assert uow._session is not None
                uow._session.add(failure_record)
                await uow.audit.record(
                    action=AuditAction.FAILURE_RECORDED,
                    entity_type="ProductionJob",
                    entity_id=job_id,
                    workflow_id=workflow_id,
                    actor="system",
                    summary=f"Production failed: {str(exc)[:150]}",
                )
                await uow.commit()
        except Exception as rollback_exc:
            logger.error("failed_to_record_production_failure", error=str(rollback_exc))
        raise exc
    finally:
        await engine.dispose()


@dramatiq.actor(queue_name="default", max_retries=3)
def run_listing_pipeline_task(workflow_id: str) -> None:
    """Entry point for Phase 8 SEO, Trademark Screening & Customer Package Generation."""
    logger.info("listing_pipeline_task_triggered", workflow_id=workflow_id)
    asyncio.run(_run_listing_pipeline_async(uuid.UUID(workflow_id)))


async def _run_listing_pipeline_async(workflow_id: uuid.UUID) -> None:
    from app.application.listing import ListingDraftService
    from app.application.package import CustomerPackageService
    from app.application.seo import generate_listing_seo
    from app.application.telegram import send_gate3_review_notification
    from app.application.trademark import TrademarkScreeningService
    from app.domain.workflow import RunStatus
    from app.providers.fake import FakeTextProvider, FakeTrademarkSearchAdapter
    from app.providers.gemini import GeminiSynthesisAdapter
    from app.providers.uspto import UsptoTrademarkAdapter

    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    storage = S3ObjectStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket_name=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region_name=settings.s3_region,
        force_path_style=settings.s3_force_path_style,
        public_endpoint_url=settings.s3_public_endpoint_url,
    )

    try:
        async with UnitOfWork(session_factory) as uow:
            workflow = await uow.workflows.get(workflow_id)
            if not workflow:
                logger.error("workflow_not_found_for_listing_pipeline", workflow_id=str(workflow_id))
                return

            concepts = await uow.concepts.list_for_workflow(workflow_id)
            if not concepts:
                logger.error("no_concepts_for_listing_pipeline", workflow_id=str(workflow_id))
                return
            concept = concepts[0]
            prompts = await uow.concepts.prompts(concept.id)
            latest_prompt = prompts[-1] if prompts else None

            # Resolve text provider
            text_provider: Any = FakeTextProvider()
            if settings.provider_mode == "live":
                cred = await uow.credentials.get(workflow.owner_id, ProviderName.GEMINI)
                if cred:
                    cipher = build_credential_cipher(settings)
                    if cipher:
                        raw_key = cipher.decrypt(cred.ciphertext, key_version=cred.key_version)
                        text_provider = GeminiSynthesisAdapter(api_key=raw_key)

            # Resolve trademark provider
            trademark_provider: Any = FakeTrademarkSearchAdapter()
            if settings.provider_mode == "live":
                cred = await uow.credentials.get(workflow.owner_id, ProviderName.USPTO)
                if cred:
                    from app.api.dependencies import build_credential_cipher

                    cipher = build_credential_cipher(settings)
                    if cipher:
                        raw_key = cipher.decrypt(cred.ciphertext, key_version=cred.key_version)
                        trademark_provider = UsptoTrademarkAdapter(api_key=raw_key)
                elif hasattr(settings, "uspto_api_key") and settings.uspto_api_key:
                    trademark_provider = UsptoTrademarkAdapter(api_key=settings.uspto_api_key.get_secret_value())

            # Keyword clusters from research
            research_runs = await uow.research.list_runs_for_workflow(workflow_id)
            keywords: list[str] = []
            for r in research_runs:
                clusters = await uow.research.get_keyword_clusters_for_run(r.id)
                for cl in clusters:
                    keywords.append(cl.primary_phrase)
                    keywords.extend(cl.attributes)

            # 1. Generate SEO Copy
            seo_draft = await generate_listing_seo(
                concept=concept,
                prompt=latest_prompt,
                keywords=keywords[:15],
                text_provider=text_provider,
            )

            listing_service = ListingDraftService()
            draft = await listing_service.get_or_create_listing(workflow_id, uow)
            await uow.listing_drafts.update(
                draft.id,
                title=seo_draft.title,
                description=seo_draft.description,
                tags=seo_draft.tags,
                ai_disclosure=seo_draft.ai_disclosure,
            )

            # 2. Trademark Screening
            trademark_service = TrademarkScreeningService(trademark_provider)
            screened_draft = await listing_service.rescreen_trademark(
                workflow_id=workflow_id,
                uow=uow,
                trademark_service=trademark_service,
            )

            # 3. Assemble Customer Package
            package_service = CustomerPackageService(storage)
            try:
                await package_service.build_customer_package(workflow_id, uow)
            except Exception as pkg_err:
                logger.warning("customer_package_builder_deferred", error=str(pkg_err))

            # 4. Advance Workflow State
            workflow.state = RunStatus.LISTING_REVIEW
            workflow.updated_at = datetime.now(UTC)

            # Audit record
            await uow.audit.record(
                action=AuditAction.WORKFLOW_TRANSITION,
                entity_type="ListingDraft",
                entity_id=draft.id,
                workflow_id=workflow_id,
                actor="system",
                summary=f"SEO generated & trademark screened (Risk: {screened_draft.ip_risk_level.value})",
            )

            # Telegram Notification
            bot_token = None
            if settings.telegram_bot_token:
                bot_token = settings.telegram_bot_token.get_secret_value()
            elif settings.provider_mode == "live":
                cred = await uow.credentials.get(workflow.owner_id, ProviderName.TELEGRAM)
                if cred:
                    cipher = build_credential_cipher(settings)
                    if cipher:
                        bot_token = cipher.decrypt(cred.ciphertext, key_version=cred.key_version)

            if settings.provider_mode == "live" and bot_token:
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    tg_gw: TelegramGateway = RealTelegramGateway(bot_token, http_client)
                    await send_gate3_review_notification(
                        uow=uow,
                        telegram_gateway=tg_gw,
                        owner_id=workflow.owner_id,
                        workflow_id=workflow_id,
                        title=screened_draft.title,
                        tags_count=len(screened_draft.tags),
                        risk_level_value=screened_draft.ip_risk_level.value,
                        web_dashboard_url="http://localhost:3000",
                    )
            else:
                fake_tg = FakeTelegramGateway()
                await send_gate3_review_notification(
                    uow=uow,
                    telegram_gateway=fake_tg,
                    owner_id=workflow.owner_id,
                    workflow_id=workflow_id,
                    title=screened_draft.title,
                    tags_count=len(screened_draft.tags),
                    risk_level_value=screened_draft.ip_risk_level.value,
                    web_dashboard_url="http://localhost:3000",
                )

            await uow.commit()
            logger.info("listing_pipeline_completed_successfully", workflow_id=str(workflow_id))

    except Exception as exc:
        logger.exception("listing_pipeline_failed", error=str(exc))
        raise exc
    finally:
        await engine.dispose()

