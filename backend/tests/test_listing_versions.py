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
    draft.version = 2
    record_version_snapshot(draft, source="manual")
    assert len(draft.ip_findings["history"]) == 2
    assert draft.ip_findings["history"][1]["version"] == 2
