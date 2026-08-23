"""Etsy OAuth 2.0 PKCE and draft dispatch endpoints."""

from __future__ import annotations

import urllib.parse
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
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
    EtsyDispatchStepInfo,
    EtsyDraftDispatchResponse,
    EtsyDraftVerificationResponse,
)
from app.application import etsy_auth, etsy_draft, etsy_verification
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
    etsy_gateway: EtsyGatewayDep,
) -> EtsyDraftDispatchResponse:
    """Validate pre-conditions and enqueue background worker task to create Etsy draft."""
    try:
        workflow, listing, conn, _, _ = await etsy_draft.validate_pre_dispatch(
            workflow_id=workflow_id,
            owner_id=user.id,
            uow=uow,
            storage=storage,
            etsy_gateway=etsy_gateway,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # If already completed, return existing result
    if (
        workflow.state == RunStatus.ETSY_DRAFT_CREATED
        and listing.etsy_dispatch_status == "completed"
    ):
        return _build_etsy_dispatch_response(workflow_id, listing)

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

    return _build_etsy_dispatch_response(workflow_id, listing, override_status="queued")


def _build_etsy_dispatch_response(
    workflow_id: uuid.UUID,
    listing: Any,
    reconcile_res: Any = None,
    override_status: str | None = None,
) -> EtsyDraftDispatchResponse:
    if listing is None:
        return EtsyDraftDispatchResponse(
            workflow_id=workflow_id,
            dispatch_status=override_status or "not_started",
            steps={
                "create_listing": EtsyDispatchStepInfo(status="pending"),
                "upload_mockups": EtsyDispatchStepInfo(status="pending"),
                "upload_files": EtsyDispatchStepInfo(status="pending"),
                "apply_attributes": EtsyDispatchStepInfo(status="pending"),
            },
        )

    dispatch_status = override_status or (
        "draft_removed"
        if reconcile_res and getattr(reconcile_res, "status", None) == "draft_removed"
        else (getattr(listing, "etsy_dispatch_status", None) or "not_started")
    )

    image_count = len(listing.etsy_image_ids or [])
    file_ids = list(
        listing.etsy_file_ids or ([listing.etsy_file_id] if listing.etsy_file_id else [])
    )
    file_count = len(file_ids)

    # Determine individual step states
    steps: dict[str, EtsyDispatchStepInfo] = {}

    # Step 1: Create Listing
    if listing.etsy_listing_id:
        steps["create_listing"] = EtsyDispatchStepInfo(status="completed")
    elif dispatch_status in ("queued", "creating_listing"):
        steps["create_listing"] = EtsyDispatchStepInfo(status="in_progress")
    elif dispatch_status == "failed" and not listing.etsy_listing_id:
        steps["create_listing"] = EtsyDispatchStepInfo(
            status="failed", error=listing.etsy_failure_reason
        )
    else:
        steps["create_listing"] = EtsyDispatchStepInfo(status="pending")

    # Step 2: Upload Mockups
    if image_count > 0 and dispatch_status in (
        "uploading_file",
        "uploading_files",
        "applying_attributes",
        "completed",
    ):
        steps["upload_mockups"] = EtsyDispatchStepInfo(
            status="completed", uploaded_count=image_count
        )
    elif dispatch_status == "uploading_images":
        steps["upload_mockups"] = EtsyDispatchStepInfo(
            status="in_progress", uploaded_count=image_count
        )
    elif dispatch_status == "failed" and listing.etsy_listing_id and image_count == 0:
        steps["upload_mockups"] = EtsyDispatchStepInfo(
            status="failed", error=listing.etsy_failure_reason
        )
    elif dispatch_status == "completed":
        steps["upload_mockups"] = EtsyDispatchStepInfo(
            status="completed", uploaded_count=image_count
        )
    else:
        steps["upload_mockups"] = EtsyDispatchStepInfo(status="pending", uploaded_count=image_count)

    # Step 3: Upload Digital Files
    if file_count > 0 and dispatch_status in ("applying_attributes", "completed"):
        steps["upload_files"] = EtsyDispatchStepInfo(status="completed", uploaded_count=file_count)
    elif dispatch_status in ("uploading_file", "uploading_files"):
        steps["upload_files"] = EtsyDispatchStepInfo(
            status="in_progress", uploaded_count=file_count
        )
    elif dispatch_status == "failed" and image_count > 0 and file_count == 0:
        steps["upload_files"] = EtsyDispatchStepInfo(
            status="failed", error=listing.etsy_failure_reason
        )
    elif dispatch_status == "completed":
        steps["upload_files"] = EtsyDispatchStepInfo(status="completed", uploaded_count=file_count)
    else:
        steps["upload_files"] = EtsyDispatchStepInfo(status="pending", uploaded_count=file_count)

    # Step 4: Apply Category Attributes
    if dispatch_status == "completed":
        steps["apply_attributes"] = EtsyDispatchStepInfo(status="completed")
    elif dispatch_status == "applying_attributes":
        steps["apply_attributes"] = EtsyDispatchStepInfo(status="in_progress")
    elif dispatch_status == "failed" and file_count > 0:
        steps["apply_attributes"] = EtsyDispatchStepInfo(
            status="failed", error=listing.etsy_failure_reason
        )
    else:
        steps["apply_attributes"] = EtsyDispatchStepInfo(status="pending")

    # Current step identifier
    current_step = None
    if dispatch_status == "creating_listing":
        current_step = "create_listing"
    elif dispatch_status == "uploading_images":
        current_step = "upload_mockups"
    elif dispatch_status in ("uploading_file", "uploading_files"):
        current_step = "upload_files"
    elif dispatch_status == "applying_attributes":
        current_step = "apply_attributes"

    taxonomy_path = getattr(listing, "taxonomy_path", None)
    if not isinstance(taxonomy_path, str):
        taxonomy_path = None

    taxonomy_id = getattr(listing, "taxonomy_id", None)
    if not isinstance(taxonomy_id, int):
        taxonomy_id = None

    etsy_listing_id = getattr(listing, "etsy_listing_id", None)
    if not isinstance(etsy_listing_id, str):
        etsy_listing_id = None

    etsy_listing_url = getattr(listing, "etsy_listing_url", None)
    if not isinstance(etsy_listing_url, str):
        etsy_listing_url = None

    etsy_state = getattr(listing, "etsy_state", None)
    if not isinstance(etsy_state, str):
        etsy_state = "draft"

    etsy_shop_id = getattr(listing, "etsy_shop_id", None)
    if not isinstance(etsy_shop_id, str):
        etsy_shop_id = None

    etsy_file_id = getattr(listing, "etsy_file_id", None)
    if not isinstance(etsy_file_id, str):
        etsy_file_id = None

    failure_reason = getattr(listing, "etsy_failure_reason", None)
    if not isinstance(failure_reason, str):
        failure_reason = None

    last_synced_at = getattr(listing, "etsy_last_synced_at", None)
    if not isinstance(last_synced_at, datetime):
        last_synced_at = None

    err_msg = (
        failure_reason
        if not (reconcile_res and reconcile_res.status == "draft_removed")
        else getattr(reconcile_res, "detail", None)
    )
    if not isinstance(err_msg, str):
        err_msg = None

    verification_data = getattr(listing, "etsy_verification_result", None)
    verification_resp = None
    if isinstance(verification_data, dict) and verification_data:
        try:
            verification_resp = EtsyDraftVerificationResponse.model_validate(verification_data)
        except Exception:
            verification_resp = None

    return EtsyDraftDispatchResponse(
        workflow_id=workflow_id,
        dispatch_status=dispatch_status,
        current_step=current_step,
        etsy_listing_id=etsy_listing_id,
        etsy_listing_url=etsy_listing_url,
        etsy_state=etsy_state,
        etsy_shop_id=etsy_shop_id,
        etsy_image_ids=list(listing.etsy_image_ids or [])
        if isinstance(getattr(listing, "etsy_image_ids", None), list)
        else [],
        etsy_file_id=etsy_file_id,
        etsy_file_ids=file_ids,
        taxonomy_id=taxonomy_id,
        taxonomy_path=taxonomy_path,
        error_message=err_msg,
        last_synced_at=last_synced_at,
        steps=steps,
        verification=verification_resp,
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
    etsy_gateway: EtsyGatewayDep,
    cipher: CipherDep,
    settings: SettingsDep,
    reconcile: bool = Query(
        default=True, description="Reconcile against Etsy if draft listing exists."
    ),
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
        return _build_etsy_dispatch_response(workflow_id, None)

    # Self-healing: if listing exists on Etsy, has digital deliverables attached, and workflow is ETSY_DRAFT_CREATED,
    # but dispatch_status is stuck in an in-progress status from an interrupted session:
    if (
        listing.etsy_listing_id
        and (listing.etsy_file_ids or listing.etsy_file_id)
        and workflow.state == RunStatus.ETSY_DRAFT_CREATED
        and listing.etsy_dispatch_status
        in (
            "queued",
            "creating_listing",
            "uploading_images",
            "uploading_file",
            "uploading_files",
            "applying_attributes",
        )
    ):
        listing = await uow.listing_drafts.update_etsy_dispatch_status(
            listing.id,
            status="completed",
            last_synced_at=datetime.now(UTC),
        )
        await uow.commit()

    reconcile_res = None
    # If reconcile is requested and listing has an active Etsy draft ID, verify existence
    if reconcile and listing.etsy_listing_id and listing.etsy_dispatch_status == "completed":
        reconcile_res = await etsy_draft.reconcile_etsy_draft(
            workflow_id=workflow_id,
            owner_id=user.id,
            uow=uow,
            etsy_gateway=etsy_gateway,
            cipher=cipher,
            settings=settings,
        )
        listing = await uow.listing_drafts.get_by_workflow(workflow_id)
        if listing is None:
            return _build_etsy_dispatch_response(workflow_id, None)

    return _build_etsy_dispatch_response(workflow_id, listing, reconcile_res)


@router.post(
    "/workflows/{workflow_id}/etsy/reconcile",
    response_model=EtsyDraftDispatchResponse,
    summary="Reconcile Etsy draft status against remote Etsy listing",
)
async def reconcile_etsy_draft_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    etsy_gateway: EtsyGatewayDep,
    cipher: CipherDep,
    settings: SettingsDep,
) -> EtsyDraftDispatchResponse:
    """Explicitly verify if the Etsy draft listing still exists in Etsy Shop Manager."""
    reconcile_res = await etsy_draft.reconcile_etsy_draft(
        workflow_id=workflow_id,
        owner_id=user.id,
        uow=uow,
        etsy_gateway=etsy_gateway,
        cipher=cipher,
        settings=settings,
    )

    listing = await uow.listing_drafts.get_by_workflow(workflow_id)
    if listing is None:
        return _build_etsy_dispatch_response(workflow_id, None)

    return _build_etsy_dispatch_response(workflow_id, listing, reconcile_res)


@router.post(
    "/workflows/{workflow_id}/etsy/verify",
    response_model=EtsyDraftVerificationResponse,
    summary="Verify actual Etsy draft listing against local expectations",
)
async def verify_etsy_draft_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    etsy_gateway: EtsyGatewayDep,
    cipher: CipherDep,
    storage: StorageDep,
) -> EtsyDraftVerificationResponse:
    """Run authoritative reconciliation comparing expected local state with live Etsy Open API v3 state."""
    if cipher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential cipher is not configured on the server",
        )
    report = await etsy_verification.verify_etsy_draft_listing(
        workflow_id=workflow_id,
        owner_id=user.id,
        uow=uow,
        cipher=cipher,
        etsy_gateway=etsy_gateway,
        storage=storage,
    )
    return EtsyDraftVerificationResponse.model_validate(report.to_dict())


@router.post(
    "/workflows/{workflow_id}/etsy/update-draft",
    response_model=EtsyDraftVerificationResponse,
    summary="Update remote Etsy listing draft with local changes and re-verify",
)
async def update_etsy_draft_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    etsy_gateway: EtsyGatewayDep,
    cipher: CipherDep,
    storage: StorageDep,
) -> EtsyDraftVerificationResponse:
    """Push current local listing draft fields (title, description, tags, section, inventory) to Etsy and re-verify."""
    if cipher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential cipher is not configured on the server",
        )
    try:
        report = await etsy_verification.update_remote_etsy_draft(
            workflow_id=workflow_id,
            owner_id=user.id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
            storage=storage,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return EtsyDraftVerificationResponse.model_validate(report.to_dict())


@router.get(
    "/workflows/{workflow_id}/etsy/verification",
    response_model=EtsyDraftVerificationResponse | None,
    summary="Get latest Etsy draft verification report for a workflow",
)
async def get_etsy_verification_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    etsy_gateway: EtsyGatewayDep,
    cipher: CipherDep,
    storage: StorageDep,
    force_recheck: bool = Query(default=False, description="Re-run verification against Etsy API."),
) -> EtsyDraftVerificationResponse | None:
    """Retrieve existing cached verification snapshot or run a fresh verification."""
    workflow = await uow.workflows.get(workflow_id)
    if workflow is None or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    listing = await uow.listing_drafts.get_by_workflow(workflow_id)
    if listing is None or not listing.etsy_listing_id:
        return None

    if force_recheck or not listing.etsy_verification_result:
        if cipher is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Credential cipher is not configured on the server",
            )
        report = await etsy_verification.verify_etsy_draft_listing(
            workflow_id=workflow_id,
            owner_id=user.id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
            storage=storage,
        )
        return EtsyDraftVerificationResponse.model_validate(report.to_dict())

    try:
        return EtsyDraftVerificationResponse.model_validate(listing.etsy_verification_result)
    except Exception:
        if cipher is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Credential cipher is not configured on the server",
            )
        report = await etsy_verification.verify_etsy_draft_listing(
            workflow_id=workflow_id,
            owner_id=user.id,
            uow=uow,
            cipher=cipher,
            etsy_gateway=etsy_gateway,
            storage=storage,
        )
        return EtsyDraftVerificationResponse.model_validate(report.to_dict())
