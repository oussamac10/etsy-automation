"""REST API endpoints for artwork color variants (dark-shirt, light-shirt, custom colors)."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CipherDep, CurrentUser, SettingsDep, StorageDep, UowDep
from app.api.schemas import ArtworkVariantResponse, CreateArtworkVariantRequest
from app.application.artwork_variants import ArtworkVariantError, ArtworkVariantService
from app.application.unit_of_work import UnitOfWork
from app.domain.artwork_variants import VariantType
from app.domain.enums import ProviderName
from app.domain.errors import EntityNotFoundError
from app.infrastructure.models import Asset
from app.infrastructure.security import CredentialCipher
from app.ports.providers import ImageGenerationProvider
from app.providers.fake import FakeImageProvider
from app.settings import Settings

router = APIRouter(prefix="/workflows/{workflow_id}/artwork-variants", tags=["artwork-variants"])


def to_variant_response(asset: Asset, url: str | None = None) -> ArtworkVariantResponse:
    """Format an Asset domain model into an ArtworkVariantResponse."""
    prov = asset.provenance or {}
    return ArtworkVariantResponse(
        id=asset.id,
        workflow_id=asset.workflow_id,
        derived_from_id=asset.derived_from_id,
        storage_key=asset.storage_key,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        checksum_sha256=asset.checksum_sha256,
        width=asset.width,
        height=asset.height,
        has_alpha=asset.has_alpha,
        variant_type=str(prov.get("variant_type", "variant")),
        variant_status=str(prov.get("variant_status", "ready")),
        title=str(prov.get("title") or "Color Variant"),
        custom_color=str(prov.get("custom_color")) if prov.get("custom_color") else None,
        custom_instructions=str(prov.get("custom_instructions")) if prov.get("custom_instructions") else None,
        prompt_version=str(prov.get("prompt_version")) if prov.get("prompt_version") else None,
        url=url,
        created_at=asset.created_at or datetime.now(UTC),
    )


async def _resolve_image_provider(
    owner_id: uuid.UUID,
    uow: UnitOfWork,
    settings: Settings,
    cipher: CredentialCipher | None,
) -> ImageGenerationProvider:
    """Resolve active live or fake image generation provider."""
    if settings.provider_mode == "live" and cipher is not None:
        # Check Gemini first, then Recraft
        gemini_cred = await uow.credentials.get(owner_id, ProviderName.GEMINI)
        if gemini_cred:
            from app.providers.gemini import GeminiImageAdapter

            raw_key = cipher.decrypt(gemini_cred.ciphertext, key_version=gemini_cred.key_version)
            return GeminiImageAdapter(api_key=raw_key)

        recraft_cred = await uow.credentials.get(owner_id, ProviderName.RECRAFT)
        if recraft_cred:
            from app.providers.recraft import RecraftImageAdapter

            raw_key = cipher.decrypt(recraft_cred.ciphertext, key_version=recraft_cred.key_version)
            return RecraftImageAdapter(api_key=raw_key)

    from app.providers.fake import FakeImageProvider

    return FakeImageProvider()


@router.get(
    "",
    response_model=list[ArtworkVariantResponse],
    summary="List all artwork color variants for a workflow",
)
async def list_artwork_variants_endpoint(
    workflow_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> list[ArtworkVariantResponse]:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    service = ArtworkVariantService(storage, FakeImageProvider())
    variants = await service.list_variants(workflow_id, uow)

    results: list[ArtworkVariantResponse] = []
    for var in variants:
        url = await storage.signed_url(var.storage_key, expires_in_seconds=3600)
        results.append(to_variant_response(var, url=url))

    return results


@router.post(
    "",
    response_model=ArtworkVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new color variant from the approved master PNG",
)
async def create_artwork_variant_endpoint(
    workflow_id: uuid.UUID,
    payload: CreateArtworkVariantRequest,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
    settings: SettingsDep,
    cipher: CipherDep,
) -> ArtworkVariantResponse:
    workflow = await uow.workflows.get(workflow_id)
    if not workflow or workflow.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workflow with that ID",
        )

    image_provider = await _resolve_image_provider(user.id, uow, settings, cipher)
    service = ArtworkVariantService(storage, image_provider)

    try:
        variant = await service.generate_variant(
            workflow_id=workflow_id,
            owner_id=user.id,
            variant_type=VariantType(payload.variant_type),
            custom_color=payload.custom_color,
            custom_instructions=payload.custom_instructions,
            uow=uow,
        )
    except ArtworkVariantError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except EntityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate color variant: {exc}",
        ) from exc

    url = await storage.signed_url(variant.storage_key, expires_in_seconds=3600)
    return to_variant_response(variant, url=url)


@router.post(
    "/{variant_id}/approve",
    response_model=ArtworkVariantResponse,
    summary="Explicitly approve an artwork color variant",
)
async def approve_artwork_variant_endpoint(
    workflow_id: uuid.UUID,
    variant_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ArtworkVariantResponse:
    service = ArtworkVariantService(storage, FakeImageProvider())
    try:
        asset = await service.approve_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=user.id,
            uow=uow,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant asset not found",
        )
    except ArtworkVariantError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    url = await storage.signed_url(asset.storage_key, expires_in_seconds=3600)
    return to_variant_response(asset, url=url)


@router.post(
    "/{variant_id}/reject",
    response_model=ArtworkVariantResponse,
    summary="Reject an artwork color variant",
)
async def reject_artwork_variant_endpoint(
    workflow_id: uuid.UUID,
    variant_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> ArtworkVariantResponse:
    service = ArtworkVariantService(storage, FakeImageProvider())
    try:
        asset = await service.reject_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=user.id,
            uow=uow,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant asset not found",
        )
    except ArtworkVariantError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    url = await storage.signed_url(asset.storage_key, expires_in_seconds=3600)
    return to_variant_response(asset, url=url)


@router.delete(
    "/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an artwork color variant",
)
async def delete_artwork_variant_endpoint(
    workflow_id: uuid.UUID,
    variant_id: uuid.UUID,
    user: CurrentUser,
    uow: UowDep,
    storage: StorageDep,
) -> None:
    service = ArtworkVariantService(storage, FakeImageProvider())
    try:
        await service.delete_variant(
            workflow_id=workflow_id,
            asset_id=variant_id,
            owner_id=user.id,
            uow=uow,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant asset not found",
        )
    except ArtworkVariantError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )
