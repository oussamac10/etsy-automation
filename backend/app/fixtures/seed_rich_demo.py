"""Seed rich demo workflows and mockup templates for high-resolution screenshots."""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.application.unit_of_work import UnitOfWork
from app.domain.enums import (
    ConceptOrigin,
    ConceptStatus,
    IdeaMode,
    Seasonality,
)
from app.domain.ideas import normalize_idea_text
from app.domain.workflow import JobStatus, RiskLevel, RunStatus
from app.infrastructure.database import create_engine, create_session_factory
from app.infrastructure.models import (
    ArtworkJob,
    Asset,
    ListingDraft,
    OriginalIdea,
    ProductConcept,
    ProductionJob,
    ProductWorkflow,
    User,
)
from app.settings import get_settings


async def seed_rich_showcase() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    async with UnitOfWork(session_factory) as uow:
        # Find dev owner
        owner_res = await uow.session.execute(
            select(User).where(User.email == "dev-owner@example.invalid")
        )
        owner = owner_res.scalar_one_or_none()
        if not owner:
            print("Owner not found! Run dev_seed first.")
            return

        # Find or Create Showcase Workflow at Gate 3 (Listing & Packaging)
        showcase_id = uuid.UUID("00000000-0000-4000-8000-000000000099")
        wf_res = await uow.session.execute(
            select(ProductWorkflow).where(ProductWorkflow.id == showcase_id)
        )
        workflow = wf_res.scalar_one_or_none()

        if not workflow:
            workflow = ProductWorkflow(
                id=showcase_id,
                owner_id=owner.id,
                name="Cottagecore Botanical Wildflower & Mushroom PNG",
                idea_mode=IdeaMode.HYBRID,
                target_marketplace="etsy",
                target_country="US",
                output_language="en",
                target_buyer="Nature lovers, DIY crafters, sublimation hobbyists",
                intended_product_uses=["t_shirt", "mug", "tote_bag"],
                state=RunStatus.LISTING_REVIEW,
                version=1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await uow.workflows.add(workflow)

            # Original Idea
            idea_text = "Botanical cottagecore wildflower bouquet with mystical autumn mushrooms and stay wild lettering"
            idea = OriginalIdea(
                workflow_id=showcase_id,
                original_text=idea_text,
                normalized_text=normalize_idea_text(idea_text),
            )
            await uow.ideas.add(idea)

            # Concept
            concept = ProductConcept(
                workflow_id=showcase_id,
                original_idea_id=idea.id,
                title="Mystical Cottagecore Botanical Mushrooms & Wildflowers",
                description="Intricately illustrated vintage mushroom cluster surrounded by golden autumn flora and subtle starry stippling.",
                origin=ConceptOrigin.HYBRID,
                differentiation="Hand-stippled vintage botanical etching with transparent cutout edges and rich warm earth palette.",
                target_buyer="Nature lovers, DIY crafters, sublimation hobbyists",
                buyer_use_case="Apparel printing, drinkware sublimation, sticker making",
                intended_product_uses=["t_shirt", "mug", "tote_bag"],
                seasonality=Seasonality.SEASONAL,
                risk_level=RiskLevel.LOW,
                risk_note="Preliminary IP screen clean. No matching live trademarks found in Nice Class 025 or 016.",
                score=Decimal("4.85"),
                score_breakdown={
                    "demand": 4.9,
                    "competition_opportunity": 4.6,
                    "seasonal_timing": 4.8,
                    "buyer_clarity": 5.0,
                    "differentiation": 4.7,
                    "product_versatility": 5.0,
                    "ip_safety": 5.0,
                },
                score_explanation="Exceptional demand indicators with low competitive saturation across autumn sublimation niches.",
                status=ConceptStatus.APPROVED,
            )
            await uow.concepts.add(concept)

            prompt = await uow.concepts.add_prompt_version(
                concept,
                positive_prompt="vintage botanical etching of wild forest mushrooms and autumn flowers, intricate stipple engraving, warm terracotta and sage palette, isolated on clean pure transparent background, crisp sharp vector-like contours",
                negative_prompt="photographic background, square bounding box, watermarks, signature, low resolution, blurry edges, clipping artifacts, cropped border",
                change_note="Refined floral stippling and enhanced autumn palette",
            )

            # Artwork Job & Assets
            artwork_job = ArtworkJob(
                workflow_id=showcase_id,
                concept_id=concept.id,
                prompt_id=prompt.id,
                provider="recraft",
                provider_model="recraftv4_1",
                idempotency_key=f"art-{showcase_id}",
                status=JobStatus.SUCCEEDED,
                attempt_count=1,
                requested_width=4500,
                requested_height=5400,
            )
            uow.session.add(artwork_job)
            await uow.session.flush()

            # Master Asset
            master_asset = Asset(
                workflow_id=showcase_id,
                artwork_job_id=artwork_job.id,
                storage_key=f"workflows/{showcase_id}/master/master_4500x5400.png",
                mime_type="image/png",
                byte_size=14205800,
                checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                width=4500,
                height=5400,
                has_alpha=True,
                has_transparent_pixels=True,
                provenance={"generator": "recraft_v4.1", "pipeline": "upscale_trim_qa"},
            )
            await uow.assets.add(master_asset)
            await uow.session.flush()

            # Production Job
            prod_job = ProductionJob(
                workflow_id=showcase_id,
                source_asset_id=master_asset.id,
                output_asset_id=master_asset.id,
                operations=["remove_background", "trim", "upscale_4500x5400", "composite_mockups"],
                idempotency_key=f"prod-{showcase_id}",
                status=JobStatus.SUCCEEDED,
                qa_passed=True,
                qa_report={
                    "status": "PASS",
                    "pixel_dimensions": "4500x5400",
                    "dpi": 300,
                    "color_profile": "sRGB IEC61966-2.1",
                    "alpha_channel": True,
                    "transparent_border_pixels": 250,
                    "cropped_content": False,
                    "contrast_ratio": "14.2:1",
                    "total_checks": 10,
                    "passed_checks": 10,
                },
            )
            uow.session.add(prod_job)

            # Listing Draft
            listing = ListingDraft(
                workflow_id=showcase_id,
                concept_id=concept.id,
                concept_version=1,
                artwork_asset_id=master_asset.id,
                title="Cottagecore Botanical Mushroom PNG Clipart | Vintage Wildflower Sublimation Design | 300 DPI Transparent Fall Graphic",
                description="""Bring mystical woodland vibes to your DIY craft projects with this high-resolution Botanical Mushroom & Wildflower PNG digital download!

🌿 WHAT'S INCLUDED:
• 1 High-Resolution Transparent PNG (4500 × 5400 px @ 300 DPI)
• 1 Print-Ready Vector-Optimized PDF
• Commercial Use License Included (Small Business up to 500 units)
• Full Sizing & Placement Guide for T-shirts, Mugs, Hoodies & Tote Bags

✨ PERFECT FOR:
Direct-to-Garment (DTG) printing, Sublimation on mugs & tumblers, DTF transfers, Stickers, Screen printing, and greeting cards.

⚠️ AI TRANSPARENCY NOTICE:
This artwork was curated, concept-engineered, and enhanced with AI generative assistance, followed by manual color balancing, background trimming, and professional 300 DPI print mastering.""",
                tags=[
                    "cottagecore png",
                    "vintage mushroom",
                    "botanical clipart",
                    "sublimation design",
                    "fall png graphic",
                    "woodland nature",
                    "tshirt sublimation",
                    "transparent png",
                    "printable art",
                    "aesthetic mushroom",
                    "digital download",
                    "commercial use png",
                    "300 dpi clipart",
                ],
                price_minor_units=499,
                currency="USD",
                quantity=999,
                sku="BOT-FALL-MUSH-001",
                shop_section_name="Fall & Botanical PNGs",
                ai_disclosure="This artwork was created with AI concept assistance and hand-tuned in high-resolution 300 DPI.",
                ip_reviewed_phrase="Cottagecore Botanical Mushroom",
                ip_risk_level=RiskLevel.LOW,
                ip_findings={
                    "status": "CLEAR",
                    "risk_level": "low",
                    "uspto_query": "Cottagecore Botanical Mushroom",
                    "exact_matches_found": 0,
                    "trigram_candidates_screened": 42,
                    "high_risk_flags": [],
                    "screened_at": datetime.now(UTC).isoformat(),
                },
                ip_acknowledged_at=datetime.now(UTC),
                ip_acknowledged_by="dev-owner@example.invalid",
            )
            uow.session.add(listing)
            await uow.commit()
            print(f"Showcase workflow {showcase_id} seeded successfully!")
        else:
            workflow.state = RunStatus.LISTING_REVIEW
            await uow.commit()
            print(f"Showcase workflow {showcase_id} updated to LISTING_REVIEW.")


if __name__ == "__main__":
    asyncio.run(seed_rich_showcase())
