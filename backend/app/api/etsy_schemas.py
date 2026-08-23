"""Pydantic schemas for Etsy OAuth and draft dispatch endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EtsyConnectResponse(BaseModel):
    """Returned when initiating Etsy OAuth 2.0 PKCE connection."""

    authorization_url: str = Field(
        ..., description="Etsy consent page URL with PKCE challenge and state."
    )


class EtsyConnectionStatusResponse(BaseModel):
    """Safe representation of the owner's Etsy shop connection. Never exposes tokens."""

    connected: bool = Field(..., description="True if shop connection is established.")
    shop_id: str | None = Field(default=None, description="Connected Etsy shop ID.")
    shop_name: str | None = Field(default=None, description="Connected Etsy shop display name.")
    connection_status: str = Field(
        default="disconnected",
        description="Current status: connected, refresh_required, reauthorization_required, disconnected.",
    )
    granted_scopes: list[str] = Field(
        default_factory=list, description="OAuth scopes granted by seller."
    )
    token_health: str = Field(
        default="disconnected",
        description="Health of the token: valid, refresh_required, reauthorization_required, disconnected.",
    )
    token_expires_at: datetime | None = Field(
        default=None, description="Expiration time of active access token."
    )
    last_refreshed_at: datetime | None = Field(
        default=None, description="Last successful token refresh timestamp."
    )


class EtsyDispatchStepInfo(BaseModel):
    """Details for an individual step in the Etsy dispatch pipeline."""

    status: str = Field(
        default="pending", description="pending, in_progress, completed, failed, skipped"
    )
    uploaded_count: int = Field(default=0, description="Count of items successfully uploaded.")
    total_count: int | None = Field(default=None, description="Total items planned.")
    error: str | None = Field(default=None, description="Error detail if step failed.")


class EtsyVerificationCheckResponse(BaseModel):
    key: str = Field(
        ..., description="Check identifier (e.g. title, price, digital_files, ai_disclosure)"
    )
    label: str = Field(..., description="Human-readable label for the check")
    category: str = Field(
        ...,
        description="Category: listing, commerce, media_and_delivery, attributes, manual_review",
    )
    status: str = Field(
        ..., description="synced, different, missing, failed, manual_review, not_applicable"
    )
    expected: Any = Field(default=None, description="Expected local value")
    actual: Any = Field(
        default=None, description="Authoritative actual value from Etsy Open API v3"
    )
    message: str | None = Field(default=None, description="Explanation of difference or guidance")
    source: str = Field(default="etsy_api", description="Source: etsy_api or manual_review")
    details: dict[str, Any] | None = Field(
        default=None, description="Detailed sub-items (e.g. tags, properties)"
    )


class EtsyVerificationSummaryResponse(BaseModel):
    synced: int = Field(default=0, description="Count of fully synced checks")
    warnings: int = Field(default=0, description="Count of differences / warnings")
    errors: int = Field(default=0, description="Count of hard errors")
    manual_review: int = Field(default=0, description="Count of manual Etsy web checks required")
    total: int = Field(default=0, description="Total checks performed")


class EtsyDraftVerificationResponse(BaseModel):
    workflow_id: str = Field(..., description="Workflow ID")
    listing_id: str | None = Field(default=None, description="Etsy Listing ID")
    status: str = Field(..., description="Overall status: verified, needs_attention, failed")
    verified_at: datetime = Field(..., description="Verification timestamp")
    summary: EtsyVerificationSummaryResponse = Field(..., description="Summary counts")
    checks: list[EtsyVerificationCheckResponse] = Field(
        default_factory=list, description="Individual checks"
    )
    error_message: str | None = Field(default=None, description="Verification error if failed")


class EtsyDraftDispatchResponse(BaseModel):
    """Status of the Etsy draft creation and asset upload operation."""

    workflow_id: uuid.UUID = Field(..., description="Workflow ID.")
    dispatch_status: str = Field(
        ...,
        description="Status: not_started, queued, creating_listing, uploading_images, uploading_files, applying_attributes, completed, draft_removed, failed.",
    )
    current_step: str | None = Field(
        default=None, description="Current executing dispatch step name."
    )
    etsy_listing_id: str | None = Field(default=None, description="Created Etsy listing ID.")
    etsy_listing_url: str | None = Field(
        default=None, description="Direct URL to edit draft in Etsy Shop Manager."
    )
    etsy_state: str | None = Field(
        default="draft", description="Listing state on Etsy (always draft)."
    )
    etsy_shop_id: str | None = Field(
        default=None, description="Etsy shop ID where listing was created."
    )
    etsy_image_ids: list[str] = Field(
        default_factory=list, description="Uploaded mockup image IDs on Etsy."
    )
    etsy_file_id: str | None = Field(
        default=None, description="Uploaded digital download file ID on Etsy."
    )
    etsy_file_ids: list[str] = Field(
        default_factory=list, description="Uploaded digital download file IDs on Etsy."
    )
    taxonomy_id: int | None = Field(default=None, description="Etsy seller taxonomy category ID.")
    taxonomy_path: str | None = Field(
        default=None, description="Etsy seller taxonomy category full path."
    )
    error_message: str | None = Field(
        default=None, description="Human-readable error details if dispatch failed."
    )
    last_synced_at: datetime | None = Field(
        default=None, description="Last successful sync timestamp."
    )
    steps: dict[str, EtsyDispatchStepInfo] = Field(
        default_factory=dict, description="Status of individual dispatch steps."
    )
    verification: EtsyDraftVerificationResponse | None = Field(
        default=None, description="Latest Etsy draft verification report."
    )
