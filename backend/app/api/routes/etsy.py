"""Etsy OAuth 2.0 PKCE and draft dispatch endpoints."""

from __future__ import annotations

import urllib.parse
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.dependencies import (
    CipherDep,
    CurrentUser,
    EtsyGatewayDep,
    RedisDep,
    SettingsDep,
    StorageDep,
    UowDep,
)
from app.api.etsy_schemas import (
    EtsyConnectionStatusResponse,
    EtsyConnectResponse,
    EtsyDraftDispatchResponse,
)
from app.application import etsy_auth, etsy_draft
from app.domain.workflow import RunStatus

router = APIRouter(tags=["etsy"])


# --------------------------------------------------------------------------
# OAuth 2.0 PKCE Endpoints
# --------------------------------------------------------------------------


@router.get(
    "/auth/etsy/connect",
    response_model=EtsyConnectResponse,
    summary="Initiate Etsy OAuth 2.0 PKCE authorization flow",
)
async def connect_etsy(
    user: CurrentUser,
    redis: RedisDep,
    settings: SettingsDep,
) -> EtsyConnectResponse:
    """Generate Etsy PKCE consent authorization URL with server-persisted state."""
    # In offline/fake mode, redirect directly to callback for instant simulated connection
    if settings.provider_mode == "fake":
        import json
        import secrets

        state = secrets.token_urlsafe(32)
        await redis.set(
            f"etsy:oauth_state:{state}",
            json.dumps({"owner_id": str(user.id), "code_verifier": "fake_code_verifier"}),
            ex=600,
        )
        callback_url = f"{settings.etsy_redirect_uri}?code=fake_auth_code_123&state={state}"
        return EtsyConnectResponse(authorization_url=callback_url)

    try:
        url = await etsy_auth.create_oauth_connect_url(redis, user.id, settings)
        return EtsyConnectResponse(authorization_url=url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Etsy authorization URL: {exc}",
        )


@router.get(
    "/auth/etsy/callback",
    summary="Handle OAuth 2.0 callback from Etsy",
    response_class=RedirectResponse,
)
async def etsy_oauth_callback(
    request: Request,
    uow: UowDep,
    redis: RedisDep,
    cipher: CipherDep,
    etsy_gateway: EtsyGatewayDep,
    settings: SettingsDep,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    """Validate OAuth state, exchange authorization code for tokens, and redirect to web settings."""
    frontend_base = settings.etsy_frontend_redirect_url

    if error or error_description:
        msg = urllib.parse.quote(error_description or error or "Authorization denied by user.")
        return RedirectResponse(
            url=f"{frontend_base}?etsy=error&message={msg}",
            status_code=status.HTTP_302_FOUND,
        )

    if not code or not state:
        msg = urllib.parse.quote("Missing required OAuth code or state parameter.")
        return RedirectResponse(
            url=f"{frontend_base}?etsy=error&message={msg}",
            status_code=status.HTTP_302_FOUND,
        )

    if cipher is None:
        msg = urllib.parse.quote("Server credential encryption is not configured.")
        return RedirectResponse(
            url=f"{frontend_base}?etsy=error&message={msg}",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        await etsy_auth.handle_oauth_callback(
            uow=uow,
            redis=redis,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
            code=code,
            state=state,
            settings=settings,
        )
        await uow.commit()
        return RedirectResponse(
            url=f"{frontend_base}?etsy=connected",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as exc:
        msg = urllib.parse.quote(str(exc))
        return RedirectResponse(
            url=f"{frontend_base}?etsy=error&message={msg}",
            status_code=status.HTTP_302_FOUND,
        )


# --------------------------------------------------------------------------
# Etsy Integration Management Endpoints
# --------------------------------------------------------------------------


@router.get(
    "/integrations/etsy",
    response_model=EtsyConnectionStatusResponse,
    summary="Get current owner's Etsy connection status",
)
async def get_etsy_status(
    user: CurrentUser,
    uow: UowDep,
) -> EtsyConnectionStatusResponse:
    """Return safe integration information. Never returns OAuth tokens."""
    conn = await uow.shop_connections.get_by_user_id(user.id)
    if conn is None or conn.connection_status == "disconnected":
        return EtsyConnectionStatusResponse(
            connected=False,
            connection_status="disconnected",
            token_health="disconnected",
        )

    # Calculate token health
    if conn.connection_status == "reauthorization_required":
        health = "reauthorization_required"
    elif conn.is_token_expired:
        health = "refresh_required"
    else:
        health = "valid"

    return EtsyConnectionStatusResponse(
        connected=conn.is_connected,
        shop_id=conn.etsy_shop_id,
        shop_name=conn.etsy_shop_name,
        connection_status=conn.connection_status,
        granted_scopes=list(conn.granted_scopes or []),
        token_health=health,
        token_expires_at=conn.token_expires_at,
        last_refreshed_at=conn.last_refreshed_at,
    )


@router.delete(
    "/integrations/etsy",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect the Etsy shop connection",
)
async def disconnect_etsy_integration(
    user: CurrentUser,
    uow: UowDep,
) -> None:
    """Revoke local Etsy shop authorization and remove stored encrypted tokens."""
    await etsy_auth.disconnect_etsy(uow, user.id)
    await uow.commit()


# --------------------------------------------------------------------------
# Etsy Draft Creation & Status Endpoints
# --------------------------------------------------------------------------


@router.post(
    "/workflows/{workflow_id}/etsy/draft",
    response_model=EtsyDraftDispatchResponse,
    summary="Trigger asynchronous Etsy draft creation and asset upload",
)
async def create_etsy_draft_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> EtsyDraftDispatchResponse:
    """Validate pre-conditions and enqueue background worker task to create Etsy draft."""
    try:
        workflow, listing, conn, _, _ = await etsy_draft.validate_pre_dispatch(
            workflow_id=workflow_id,
            owner_id=user.id,
            uow=uow,
            storage=storage,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # If already completed, return existing result
    if workflow.state == RunStatus.ETSY_DRAFT_CREATED and listing.etsy_dispatch_status == "completed":
        return EtsyDraftDispatchResponse(
            workflow_id=workflow_id,
            dispatch_status="completed",
            etsy_listing_id=listing.etsy_listing_id,
            etsy_listing_url=listing.etsy_listing_url,
            etsy_state=listing.etsy_state,
            etsy_shop_id=listing.etsy_shop_id,
            etsy_image_ids=list(listing.etsy_image_ids or []),
            etsy_file_id=listing.etsy_file_id,
            last_synced_at=listing.etsy_last_synced_at,
        )

    # Update status to queued and add to outbox
    listing = await uow.listing_drafts.update_etsy_dispatch_status(
        listing.id,
        status="queued",
        last_synced_at=datetime.now(UTC),
    )
    await uow.outbox.add(
        "create_etsy_draft_task",
        {"workflow_id": str(workflow_id)},
    )
    await uow.commit()

    return EtsyDraftDispatchResponse(
        workflow_id=workflow_id,
        dispatch_status="queued",
        etsy_listing_id=listing.etsy_listing_id,
        etsy_listing_url=listing.etsy_listing_url,
        etsy_state=listing.etsy_state,
        etsy_shop_id=listing.etsy_shop_id,
        etsy_image_ids=list(listing.etsy_image_ids or []),
        etsy_file_id=listing.etsy_file_id,
        last_synced_at=listing.etsy_last_synced_at,
    )


@router.get(
    "/workflows/{workflow_id}/etsy/status",
    response_model=EtsyDraftDispatchResponse,
    summary="Get the Etsy draft creation status for a workflow",
)
async def get_etsy_draft_status_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
) -> EtsyDraftDispatchResponse:
    """Poll the current progress and results of the Etsy draft listing operation."""
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    listing = await uow.listing_drafts.get_by_workflow(workflow_id)
    if listing is None:
        return EtsyDraftDispatchResponse(
            workflow_id=workflow_id,
            dispatch_status="not_started",
        )

    return EtsyDraftDispatchResponse(
        workflow_id=workflow_id,
        dispatch_status=listing.etsy_dispatch_status or "not_started",
        etsy_listing_id=listing.etsy_listing_id,
        etsy_listing_url=listing.etsy_listing_url,
        etsy_state=listing.etsy_state,
        etsy_shop_id=listing.etsy_shop_id,
        etsy_image_ids=list(listing.etsy_image_ids or []),
        etsy_file_id=listing.etsy_file_id,
        error_message=listing.etsy_failure_reason,
        last_synced_at=listing.etsy_last_synced_at,
    )
