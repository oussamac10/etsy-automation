"""Request and response models.

Deliberately separate from both the ORM models and the domain: an API contract
should be able to stay stable while either of those changes, and a response
should never be able to leak a column that was added for internal use.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import IdeaMode
from app.domain.workflow import ApprovalDecision, ApprovalGate, RunStatus

CountryCode = Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")]
LanguageCode = Annotated[str, Field(min_length=2, max_length=10)]


class CreateWorkflowRequest(BaseModel):
    """No ``owner_id``.

    Ownership comes from the session, so a client cannot express the request
    "create this for someone else" — which is stronger than validating it away.
    """

    model_config = ConfigDict(extra="forbid")

    idea_mode: IdeaMode
    name: Annotated[str | None, Field(max_length=200)] = None
    target_country: CountryCode
    output_language: LanguageCode
    target_marketplace: Annotated[str, Field(max_length=50)] = "etsy"
    target_buyer: Annotated[str | None, Field(max_length=2000)] = None
    intended_product_uses: Annotated[list[str], Field(max_length=20)] = []

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name must not be blank")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def _validate_name_requirement(self) -> CreateWorkflowRequest:
        if self.idea_mode != IdeaMode.MARKET_LED and not self.name:
            raise ValueError("name is required for this idea mode")
        return self


class SubmitIdeaRequest(BaseModel):
    """The owner's own words.

    ``original_text`` is stored exactly as sent — no trimming beyond the
    surrounding whitespace a form adds, no rewriting, no normalisation. The
    normalised form is derived and stored separately.
    """

    model_config = ConfigDict(extra="forbid")

    original_text: Annotated[str, Field(min_length=3, max_length=4000)]
    slogan: Annotated[str | None, Field(max_length=300)] = None
    desired_style: Annotated[str | None, Field(max_length=300)] = None
    audience: Annotated[str | None, Field(max_length=300)] = None
    occasion: Annotated[str | None, Field(max_length=200)] = None
    season: Annotated[str | None, Field(max_length=100)] = None
    product_uses: Annotated[list[str], Field(max_length=20)] = []


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    idea_mode: IdeaMode
    name: str
    target_marketplace: str
    target_country: str
    output_language: str
    target_buyer: str | None
    intended_product_uses: list[str]
    state: RunStatus
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    limit: int
    offset: int


class OriginalIdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    #: The owner's verbatim submission. Never an optimised rewrite.
    original_text: str
    slogan: str | None
    desired_style: str | None
    audience: str | None
    occasion: str | None
    season: str | None
    product_uses: list[str]
    revision_count: int
    created_at: datetime


class TimelineEntryResponse(BaseModel):
    kind: str
    occurred_at: str
    summary: str
    detail: dict[str, object]


class TimelineResponse(BaseModel):
    workflow_id: uuid.UUID
    state: RunStatus
    entries: list[TimelineEntryResponse]


class GateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate: ApprovalGate
    decision: ApprovalDecision
    # No `actor`: an approval is the evidence a human decided, so the name on it
    # comes from the session, not from the body. `extra="forbid"` makes sending
    # one a 422 rather than a silently ignored field.
    comment: Annotated[str | None, Field(max_length=4000)] = None
    revision_request: Annotated[str | None, Field(max_length=4000)] = None
    #: What was reviewed. An approval refers to a version, not just an entity.
    target_type: Annotated[str, Field(max_length=60)] = "ProductWorkflow"
    target_id: uuid.UUID | None = None
    target_version: int | None = None

    @field_validator("gate", mode="before")
    @classmethod
    def normalize_gate(cls, v: object) -> object:
        if isinstance(v, str):
            v_upper = v.upper()
            for member in ApprovalGate:
                if member.value == v_upper or member.name == v_upper:
                    return member
        return v

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, v: object) -> object:
        if isinstance(v, str):
            v_upper = v.upper()
            for member in ApprovalDecision:
                if member.value == v_upper or member.name == v_upper:
                    return member
        return v


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    gate: ApprovalGate
    decision: ApprovalDecision
    actor: str
    comment: str | None
    revision_request: str | None
    previous_state: RunStatus
    resulting_state: RunStatus
    target_type: str
    target_version: int | None
    decided_at: datetime | None
    created_at: datetime


class ResearchRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    run_number: int
    status: str
    confidence: str | None
    proposed_test: str | None
    started_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None
    query_angles: list[str]


class ResearchEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    search_query: str
    query_angle: str
    source_url: str
    source_title: str
    source_type: str
    observation: str
    observed_at: datetime


class KeywordClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    primary_phrase: str
    attributes: list[str]
    recipient_occasion_terms: list[str]
    use_case_terms: list[str]
    competition_level: str
    competition_note: str | None
    relevance_rank: int


class ResearchSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run: ResearchRunResponse | None = None
    evidence: list[ResearchEvidenceResponse] = []
    keyword_clusters: list[KeywordClusterResponse] = []
    proven_market_observations: list[str] = []


class DesignPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    concept_id: uuid.UUID
    version: int
    positive_prompt: str
    negative_prompt: str
    typography_instructions: str | None
    exact_slogan: str | None
    intended_product_uses: list[str]
    style_notes: str | None
    palette: str | None
    post_generation_checklist: list[str]
    generation_metadata: dict[str, object]
    change_note: str | None
    created_at: datetime


class ProductConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    original_idea_id: uuid.UUID | None
    research_run_id: uuid.UUID | None
    title: str
    description: str
    origin: str
    differentiation: str
    target_buyer: str | None
    buyer_use_case: str | None
    seasonality: str
    risk_level: str
    risk_note: str | None
    score: float | None
    score_breakdown: dict[str, object]
    score_explanation: str | None
    status: str
    created_at: datetime
    intended_product_uses: list[str] = []
    prompts: list[DesignPromptResponse] = []


class UpdateMockupSuggestionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[str] = []


class ConceptRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positive_prompt: str
    negative_prompt: str
    typography_instructions: str | None = None
    exact_slogan: str | None = None
    change_note: Annotated[str, Field(min_length=1, max_length=1000)]


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    artwork_job_id: uuid.UUID | None
    derived_from_id: uuid.UUID | None
    storage_key: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    width: int | None
    height: int | None
    has_alpha: bool | None
    has_transparent_pixels: bool | None
    provenance: dict[str, object]
    created_at: datetime
    url: str | None = None


class ArtworkJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    concept_id: uuid.UUID
    prompt_id: uuid.UUID
    provider: str
    provider_model: str | None
    provider_job_id: str | None
    idempotency_key: str
    status: str
    attempt_count: int
    requested_width: int | None
    requested_height: int | None
    quality: str | None
    started_at: datetime | None
    completed_at: datetime | None
    failure_kind: str | None
    failure_message: str | None
    created_at: datetime
    assets: list[AssetResponse] = []


class GenerateArtworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    provider_model: str | None = None
    requested_width: int | None = 1024
    requested_height: int | None = 1024
    quality: str | None = "standard"


class RefineArtworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_asset_id: uuid.UUID
    positive_prompt: str
    negative_prompt: str | None = None
    change_note: Annotated[str, Field(min_length=1, max_length=1000)]


class StartProductionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_new: bool = False
    candidate_asset_id: uuid.UUID | None = None


class ProductionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    source_asset_id: uuid.UUID | None
    output_asset_id: uuid.UUID | None
    operations: list[str]
    status: str
    idempotency_key: str
    attempt_count: int
    qa_report: dict[str, object]
    qa_passed: bool | None
    started_at: datetime | None
    completed_at: datetime | None
    failure_kind: str | None
    failure_message: str | None
    created_at: datetime
    master_asset: AssetResponse | None = None
    mockup_assets: list[AssetResponse] = []
    mockup_urls: dict[str, str] = {}


class ReorderMockupsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[uuid.UUID]


class UpdateListingDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=140)]
    description: Annotated[str, Field(min_length=1)]
    tags: Annotated[list[str], Field(min_length=13, max_length=13)]
    taxonomy_id: int | None = None
    taxonomy_path: str | None = None
    price_minor_units: Annotated[int, Field(ge=20, le=100000)] | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] | None = None
    quantity: Annotated[int, Field(ge=1, le=9999)] | None = None
    sku: Annotated[str, Field(max_length=64)] | None = None
    shop_section_id: Annotated[str, Field(max_length=64)] | None = None
    shop_section_name: Annotated[str, Field(max_length=128)] | None = None
    should_auto_renew: bool | None = None
    etsy_properties: dict[str, Any] | None = None
    primary_mockup_asset_id: uuid.UUID | None = None
    shopping_cart_summary: str | None = None
    expected_version: int | None = None


class Gate3DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ApprovalDecision
    acknowledged: bool = False

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, v: object) -> object:
        if isinstance(v, str):
            v_upper = v.upper()
            for member in ApprovalDecision:
                if member.value == v_upper or member.name == v_upper:
                    return member
        return v


class ListingDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    title: str
    description: str
    tags: list[str]
    taxonomy_id: int | None = None
    taxonomy_path: str | None = None
    taxonomy_selection_source: str | None = "auto"
    price_minor_units: int | None = None
    currency: str = "USD"
    quantity: int = 999
    sku: str | None = None
    shop_section_id: str | None = None
    shop_section_name: str | None = None
    should_auto_renew: bool = False
    etsy_properties: dict[str, object] = {}
    primary_mockup_asset_id: uuid.UUID | None = None
    shopping_cart_summary: str | None = None
    ai_disclosure: str | None = None
    licence_text: str | None = None
    customer_instructions: str | None = None
    ip_reviewed_phrase: str | None = None
    ip_risk_level: str
    ip_findings: dict[str, object]
    ip_acknowledged_at: datetime | None = None
    ip_acknowledged_by: str | None = None
    version: int
    package_asset: AssetResponse | None = None
    package_download_url: str | None = None
    history: list[dict[str, object]] = []
    tag_history: list[str] = []
    etsy_listing_id: str | None = None
    etsy_listing_url: str | None = None
    etsy_dispatch_status: str | None = None
    etsy_image_ids: list[str] | None = None
    etsy_file_id: str | None = None
    etsy_file_ids: list[str] | None = None
    etsy_failure_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RestoreListingVersionRequest(BaseModel):
    version: int = Field(..., ge=1, description="Version number to restore")


class TaxonomyCategoryResponse(BaseModel):
    id: int
    name: str
    full_path: str
    level: int
    fit_score: float | None = None
    fit_level: str | None = None
    blocking_mismatch: bool = False
    fit_reasons: list[str] = []
    warnings: list[str] = []


class TaxonomyFitnessResponse(BaseModel):
    taxonomy_id: int
    taxonomy_path: str
    fit: str = "good"
    score: float = 1.0
    fit_score: float = 1.0
    fit_level: str = "good"
    blocking_mismatch: bool = False
    fit_reasons: list[str] = []
    warnings: list[str] = []
    has_mismatched_required_attributes: bool = False
    mismatched_required_reason: str | None = None
    best_available: bool = False
    campaign_intent: str = "apparel_sublimation"


class ShopSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_section_id: str
    title: str
    rank: int = 0
    active_listing_count: int = 0


class CreateShopSectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=120)]


class TaxonomyPropertyResponse(BaseModel):
    property_id: int
    name: str
    display_name: str | None = None
    is_required: bool = False
    supports_attributes: bool = False
    supports_variations: bool = False
    is_multivalued: bool = False
    max_values_allowed: int | None = None
    scales: list[dict[str, Any]] = []
    possible_values: list[dict[str, Any]] = []


class PriceRecommendationResponse(BaseModel):
    recommended_minor_units: int
    currency: str
    formatted_price: str
    rationale: str
    factors: list[str] = []


class UpdateListingTaxonomyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy_id: int
    taxonomy_path: str | None = None


class ReResolveTaxonomyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apply: bool = False


class ReResolveTaxonomyResponse(BaseModel):
    recommended_taxonomy_id: int
    recommended_taxonomy_path: str
    fit_score: float
    fit_level: str
    blocking_mismatch: bool
    fit_reasons: list[str] = []
    warnings: list[str] = []
    applied: bool = False
    current_taxonomy_id: int | None = None
    current_taxonomy_path: str | None = None


class CreateArtworkVariantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_type: Annotated[str, Field(pattern=r"^(dark_shirt|light_shirt|black_accent|white_accent|custom)$")]
    custom_color: str | None = None
    target_color: str | None = None
    darkness_threshold: float | None = None
    custom_instructions: str | None = None


class UpdateArtworkVariantPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_in_buyer_package: bool


class ArtworkVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    derived_from_id: uuid.UUID | None
    storage_key: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    width: int | None
    height: int | None
    has_alpha: bool | None
    variant_type: str
    variant_status: str
    title: str
    custom_color: str | None = None
    custom_instructions: str | None = None
    prompt_version: str | None = None
    url: str | None = None
    include_in_buyer_package: bool = False
    source_outdated: bool = False
    validation_report: dict[str, Any] | None = None
    created_at: datetime


class PackageFileItem(BaseModel):
    type: str
    name: str
    filename: str
    byte_size: int
    included: bool
    status: str
    asset_id: str | None = None


class BuyerPackagePreviewResponse(BaseModel):
    workflow_id: uuid.UUID
    files: list[PackageFileItem]
    included_count: int
    estimated_total_bytes: int
    needs_rebuild: bool
    etsy_files_out_of_sync: bool
    package_asset: AssetResponse | None = None
    package_download_url: str | None = None




