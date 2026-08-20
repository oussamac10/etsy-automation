import uuid
import pytest
from app.application.listing import (
    ListingDraftService,
    deduplicate_history,
    record_version_snapshot,
)
from app.infrastructure.models.listing import ListingDraft
from app.domain.workflow import RiskLevel


def test_deduplicate_history():
    history = [
        {"version": 1, "title": "Cat Shirt", "description": "Cute cat", "tags": ["cat", "shirt"]},
        {"version": 2, "title": "Cat Shirt", "description": "Cute cat", "tags": ["shirt", "cat"]},
        {"version": 3, "title": "Dog Shirt", "description": "Cute dog", "tags": ["dog", "shirt"]},
    ]
    cleaned = deduplicate_history(history)
    assert len(cleaned) == 2
    assert cleaned[0]["version"] == 1
    assert cleaned[1]["version"] == 3


def test_record_version_snapshot_deduplication():
    draft = ListingDraft(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        title="Floral PNG",
        description="Botanical artwork",
        tags=["floral", "botanical"],
        ip_risk_level=RiskLevel.LOW,
        ip_findings={},
        version=1,
    )
    # First snapshot
    record_version_snapshot(draft, source="ai_generated")
    assert len(draft.ip_findings["history"]) == 1
    assert draft.ip_findings["history"][0]["version"] == 1

    # Second call with identical content should NOT add duplicate
    record_version_snapshot(draft, source="manual")
    assert len(draft.ip_findings["history"]) == 1

    # Third call with different title should add new snapshot
    draft.title = "Floral PNG Bundle"
    draft.tags = ["floral", "botanical", "vintage flower"]
    draft.version = 2
    record_version_snapshot(draft, source="manual")
    assert len(draft.ip_findings["history"]) == 2
    assert draft.ip_findings["history"][1]["version"] == 2
    assert "vintage flower" in draft.ip_findings["tag_history"]
    assert "floral" in draft.ip_findings["tag_history"]


def test_tag_history_accumulation():
    draft = ListingDraft(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        title="Cat PNG",
        description="Cute cat graphic",
        tags=["cat", "kitten", "feline"],
        ip_risk_level=RiskLevel.LOW,
        ip_findings={},
        version=1,
    )
    record_version_snapshot(draft, source="initial")
    assert set(draft.ip_findings["tag_history"]) == {"cat", "kitten", "feline"}

    # User replaces tags with new ones
    draft.tags = ["cat", "meow", "sublimation"]
    draft.version = 2
    record_version_snapshot(draft, source="manual")

    # All 5 historical tags are retained
    assert set(draft.ip_findings["tag_history"]) == {"cat", "kitten", "feline", "meow", "sublimation"}


@pytest.mark.asyncio
async def test_listing_creation_with_gateway_resolves_property_aware():
    from datetime import UTC, datetime
    from app.domain.enums import ConceptStatus
    from app.infrastructure.models import ProductWorkflow, ProductConcept
    from app.providers.fake import FakeEtsyProvider
    from unittest.mock import AsyncMock, MagicMock

    workflow_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    wf = ProductWorkflow(
        id=workflow_id,
        owner_id=owner_id,
        name="Retro Camping Dog PNG Sublimation Design",
        created_at=datetime.now(UTC) if "datetime" in globals() else None,
    )
    concept = ProductConcept(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        status=ConceptStatus.APPROVED,
        title="Retro Camping Dog Sublimation Graphic",
        description="Transparent PNG for T-shirts and mugs.",
        differentiation="Distressed outdoor vintage vibe",
        intended_product_uses=["t_shirt", "sweatshirt", "sublimation", "mug"],
    )

    uow = MagicMock()
    uow.listing_drafts.get_by_workflow = AsyncMock(return_value=None)
    uow.workflows.get = AsyncMock(return_value=wf)
    uow.concepts.list_for_workflow = AsyncMock(return_value=[concept])
    uow.concepts.prompts = AsyncMock(return_value=[])
    uow.owner_settings.get_for_user = AsyncMock(return_value=None)
    uow.credentials.get = AsyncMock(return_value=None)
    uow.listing_drafts.add = AsyncMock()

    service = ListingDraftService()
    fake_gateway = FakeEtsyProvider()

    draft = await service.get_or_create_listing(
        workflow_id=workflow_id,
        uow=uow,
        etsy_gateway=fake_gateway,
    )

    # Must resolve to category 77 (Digital Drawing with Sublimation Craft type), NOT papercraft 6844
    assert draft.taxonomy_id != 6844
    assert draft.taxonomy_id == 77
    assert draft.ip_findings.get("taxonomy_selection_source") == "auto"


@pytest.mark.asyncio
async def test_re_evaluate_taxonomy_preserves_existing_until_applied():
    from app.domain.enums import ConceptStatus
    from app.infrastructure.models import ProductWorkflow, ProductConcept
    from app.providers.fake import FakeEtsyProvider
    from unittest.mock import AsyncMock, MagicMock

    workflow_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    wf = ProductWorkflow(
        id=workflow_id,
        owner_id=owner_id,
        name="Camping Dog Sublimation",
    )
    concept = ProductConcept(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        status=ConceptStatus.APPROVED,
        title="Camping Dog Sublimation",
        description="For T-shirts and mugs",
        differentiation="Outdoor dog",
        intended_product_uses=["t_shirt", "sublimation"],
    )
    draft = ListingDraft(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        title="Camping Dog PNG Sublimation Design",
        description="Transparent PNG file",
        tags=["sublimation", "dog shirt", "pod graphic"],
        taxonomy_id=6844,
        taxonomy_path="Craft Supplies & Tools > Canvas & Surfaces > Clip Art",
        ip_risk_level=RiskLevel.LOW,
        ip_findings={"taxonomy_selection_source": "fallback"},
        version=1,
    )

    uow = MagicMock()
    uow.workflows.get = AsyncMock(return_value=wf)
    uow.listing_drafts.get_by_workflow = AsyncMock(return_value=draft)
    uow.concepts.list_for_workflow = AsyncMock(return_value=[concept])
    uow.concepts.prompts = AsyncMock(return_value=[])
    uow.commit = AsyncMock()

    service = ListingDraftService()
    fake_gateway = FakeEtsyProvider()

    # Call with apply = False
    res_not_applied = await service.re_evaluate_taxonomy(
        workflow_id=workflow_id,
        uow=uow,
        etsy_gateway=fake_gateway,
        apply=False,
    )
    assert res_not_applied["recommended_taxonomy_id"] == 77
    assert res_not_applied["applied"] is False
    assert draft.taxonomy_id == 6844  # Not modified

    # Call with apply = True
    res_applied = await service.re_evaluate_taxonomy(
        workflow_id=workflow_id,
        uow=uow,
        etsy_gateway=fake_gateway,
        apply=True,
    )
    assert res_applied["recommended_taxonomy_id"] == 77
    assert res_applied["applied"] is True
    assert draft.taxonomy_id == 77
    assert draft.ip_findings["taxonomy_selection_source"] == "auto"


