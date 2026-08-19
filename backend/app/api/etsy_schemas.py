"""Pydantic schemas for Etsy OAuth and draft dispatch endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class EtsyConnectResponse(BaseModel):
    """Returned when initiating Etsy OAuth 2.0 PKCE connection."""

    authorization_url: str = Field(..., description="Etsy consent page URL with PKCE challenge and state.")


class EtsyConnectionStatusResponse(BaseModel):
    """Safe representation of the owner's Etsy shop connection. Never exposes tokens."""

    connected: bool = Field(..., description="True if shop connection is established.")
    shop_id: str | None = Field(default=None, description="Connected Etsy shop ID.")
    shop_name: str | None = Field(default=None, description="Connected Etsy shop display name.")
    connection_status: str = Field(
        default="disconnected",
        description="Current status: connected, refresh_required, reauthorization_required, disconnected.",
    )
    granted_scopes: list[str] = Field(default_factory=list, description="OAuth scopes granted by seller.")
    token_health: str = Field(
        default="disconnected",
        description="Health of the token: valid, refresh_required, reauthorization_required, disconnected.",
    )
    token_expires_at: datetime | None = Field(default=None, description="Expiration time of active access token.")
    last_refreshed_at: datetime | None = Field(default=None, description="Last successful token refresh timestamp.")


class EtsyDraftDispatchResponse(BaseModel):
    """Status of the Etsy draft creation and asset upload operation."""

    workflow_id: uuid.UUID = Field(..., description="Workflow ID.")
    dispatch_status: str = Field(
        ...,
        description="Status: not_started, queued, creating_listing, uploading_images, uploading_file, completed, failed.",
    )
    etsy_listing_id: str | None = Field(default=None, description="Created Etsy listing ID.")
    etsy_listing_url: str | None = Field(
        default=None, description="Direct URL to edit draft in Etsy Shop Manager."
    )
    etsy_state: str | None = Field(default="draft", description="Listing state on Etsy (always draft).")
    etsy_shop_id: str | None = Field(default=None, description="Etsy shop ID where listing was created.")
    etsy_image_ids: list[str] = Field(default_factory=list, description="Uploaded mockup image IDs on Etsy.")
    etsy_file_id: str | None = Field(default=None, description="Uploaded digital download file ID on Etsy.")
    error_message: str | None = Field(default=None, description="Human-readable error details if dispatch failed.")
    last_synced_at: datetime | None = Field(default=None, description="Last successful sync timestamp.")
