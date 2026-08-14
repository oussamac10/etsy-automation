from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import dramatiq
from dramatiq.middleware import CurrentMessage

from app.application.owner_settings import reveal_credential
from app.application.research import ensure_research_within_budget
from app.application.unit_of_work import UnitOfWork
from app.domain import ip_risk
from app.domain.enums import (
    AuditAction,
    CompetitionLevel,
    ConceptOrigin,
    ConceptStatus,
    ConfidenceLevel,
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
from app.infrastructure.models import (
    KeywordCluster,
    ProductConcept,
    ResearchEvidence,
)
from app.infrastructure.security import CredentialCipher
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import (
    ResearchProvider,
    SearchQuery,
    SearchResult,
    TextGenerationProvider,
    TextRequest,
)

# Providers
from app.providers.fake import FakeResearchProvider, FakeTextProvider
from app.providers.openai import OpenAISynthesisAdapter
from app.providers.search import TavilySearchAdapter
from app.settings import Settings, get_settings
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
            asyncio.run(
                _mark_failure_async(uuid.UUID(workflow_id), uuid.UUID(run_id), exc.message)
            )
            return

        delay_ms = int(retry_after(exc, attempt) * 1000)
        logger.info(
            "research_task_retry_scheduled",
            delay_ms=delay_ms,
            attempt=attempt,
            message=exc.message,
        )
        raise dramatiq.errors.Retry(delay=delay_ms) from exc
    except Exception as exc:
        logger.exception("research_task_unhandled_failure", error=str(exc))
        asyncio.run(_mark_failure_async(uuid.UUID(workflow_id), uuid.UUID(run_id), str(exc)))
        # Re-raised after the run is marked failed so an unclassified bug still
        # reaches Dramatiq's dead letter queue instead of vanishing.
        raise


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
            from app.infrastructure.models.audit import WorkflowFailure
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

            openai_api_key: str | None = None
            tavily_api_key: str | None = None

            if settings.provider_mode == "live":
                cipher = build_credential_cipher(settings)
                try:
                    openai_api_key = await reveal_credential(
                        uow,
                        workflow.owner_id,
                        provider=ProviderName.OPENAI,
                        cipher=cipher,
                    )
                except Exception as exc:
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider="openai",
                        operation="resolve_credential",
                        message="OpenAI API Key is missing or invalid in credentials.",
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
        angles = {
            "broad": f"{target_theme} png design clipart",
            "long-tail": f"hand-drawn {target_theme} sublimation transparent background",
            "recipient": f"{idea_buyer or 'gift'} {target_theme} png",
            "style": f"{idea_style or 'retro groovy'} {target_theme} clipart",
            "use-case": f"{target_theme} sublimation design for mug shirt",
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

        # 3. Synthesize Findings using Text Provider (OpenAI or Fake)
        text_provider: TextGenerationProvider
        if settings.provider_mode == "live" and openai_api_key:
            text_provider = OpenAISynthesisAdapter(api_key=openai_api_key)
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
            "  \"confidence\": \"high\" | \"medium\" | \"low\",\n"
            "  \"proposed_test\": \"string outlining how to test if confidence is low\",\n"
            "  \"keyword_clusters\": [\n"
            "    {\n"
            "      \"primary_phrase\": \"string\",\n"
            "      \"attributes\": [\"string\"],\n"
            "      \"recipient_occasion_terms\": [\"string\"],\n"
            "      \"use_case_terms\": [\"string\"],\n"
            "      \"competition_level\": \"saturated\" | \"crowded\" | "
            "\"differentiable\" | \"thin\",\n"
            "      \"competition_note\": \"string detailing why this level was selected\",\n"
            "      \"relevance_rank\": int (0 to 100)\n"
            "    }\n"
            "  ],\n"
            "  \"concepts\": [\n"
            "    {\n"
            "      \"title\": \"string\",\n"
            "      \"description\": \"string\",\n"
            "      \"differentiation\": \"string stating plain differentiator (do not say "
            "'same but prettier')\",\n"
            "      \"target_buyer\": \"string\",\n"
            "      \"buyer_use_case\": \"string\",\n"
            "      \"seasonality\": \"evergreen\" | \"seasonal\" | \"both\",\n"
            "      \"risk_level\": \"low\" | \"medium\" | \"high\",\n"
            "      \"risk_note\": \"string detailed brand/IP trademark warnings\",\n"
            "      \"score_breakdown\": {\n"
            "        \"demand\": int (1 to 5),\n"
            "        \"competition_opportunity\": int (1 to 5),\n"
            "        \"seasonal_timing\": int (1 to 5),\n"
            "        \"buyer_clarity\": int (1 to 5),\n"
            "        \"differentiation\": int (1 to 5),\n"
            "        \"product_versatility\": int (1 to 5),\n"
            "        \"ip_safety\": int (1 to 5)\n"
            "      },\n"
            "      \"score_explanation\": \"string summary of how the scores compare\",\n"
            "      \"fidelity\": \"High\" | \"Medium\" | \"Low\",\n"
            "      \"origin\": \"user\" | \"market\" | \"hybrid\",\n"
            "      \"prompt\": {\n"
            "        \"positive_prompt\": \"string detailing central subject, style, "
            "composition, details, palette, isolated artwork on a transparent background\",\n"
            "        \"negative_prompt\": \"string detailing elements to reject "
            "(background, mockups, watermarks, etc.)\",\n"
            "        \"typography_instructions\": \"string or null detailing font, layout, "
            "placement\",\n"
            "        \"exact_slogan\": \"string or null detailing exact text slogans\",\n"
            "        \"intended_product_uses\": [\"string\"],\n"
            "        \"style_notes\": \"string or null\",\n"
            "        \"palette\": \"string or null\",\n"
            "        \"post_generation_checklist\": [\"string\"],\n"
            "        \"generation_metadata\": {}\n"
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "\n"
            "Rules to strictly follow:\n"
            "1. If a personal idea or user idea is provided, the first concept MUST be a "
            "faithful concept that preserves the core concept and slogan verbatim and marks "
            "fidelity as 'High'.\n"
            "2. Never name living artists in the positive prompt. Style must be descriptive "
            "(e.g. textured watercolor shading, vintage retro groovy style).\n"
            "3. Every prompt must demand 'isolated central artwork on a transparent background' "
            "and 'clean uncropped edges'.\n"
            "4. Keep typography separate. Slogans should be null in the positive prompt, "
            "and exact phrases must be listed in exact_slogan and layout instructions in "
            "typography_instructions.\n"
            "5. Never invent or include fake search volume numbers."
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
                f"Original User Idea: {user_idea_text}\n"
                f"User Slogan: {idea_slogan}\n"
                f"User Style Direction: {idea_style}\n"
                f"User Season: {idea_season}\n"
            )
        user_prompt += f"\nSearch Evidence Collected:\n{evidence_content}\n"

        # Record estimate in ledger before paid call
        estimated_price = Money(1, "USD")
        is_live = settings.provider_mode == "live"
        async with UnitOfWork(session_factory) as uow:
            ledger_entry = await uow.costs.record_estimate(
                workflow_id=workflow_id,
                provider=ProviderName.OPENAI if is_live else ProviderName.FAKE,
                service="synthesis",
                operation="research_synthesis",
                estimated=estimated_price,
                input_units=len(user_prompt.split()),
                output_units=500,
                unit_kind="tokens",
                idempotency_key=f"cost-research-synthesis-{run_id}",
            )
            await uow.commit()

        logger.info("running_openai_structured_synthesis")
        text_response = await text_provider.generate(
            TextRequest(prompt=user_prompt, system=system_prompt)
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
            cost_in = Money(int(tokens_in * 0.015), "USD") if is_live else Money(0, "USD")
            cost_out = Money(int(tokens_out * 0.060), "USD") if is_live else Money(0, "USD")
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


def build_credential_cipher(settings: Settings) -> CredentialCipher:
    """Build a helper to decrypt credentials in background workers."""
    from app.api.dependencies import build_credential_cipher as api_build
    cipher = api_build(settings)
    if not cipher:
        raise ValueError("Cipher configuration missing or invalid. Check ENCRYPTION_KEY.")
    return cipher
