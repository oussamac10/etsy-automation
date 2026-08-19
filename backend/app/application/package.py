"""Application service for assembling customer download ZIP packages."""

from __future__ import annotations

import hashlib
import re
import uuid
import structlog

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import EntityNotFoundError
from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
)
from app.domain.production_resolver import (
    filter_active_user_mockups,
    get_production_master_asset,
)
from app.infrastructure.models import Asset, ListingDraft, ProductWorkflow
from app.ports.providers import ObjectStorage

logger = structlog.get_logger(__name__)


class CustomerPackageService:
    """Builds and stores deterministic customer ZIP packages."""

    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    async def build_customer_package(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
        *,
        include_mockups: bool = True,
    ) -> Asset:
        """Assemble customer ZIP package from master artwork, optional mockups, and legal documents."""
        workflow: ProductWorkflow | None = await uow.workflows.get(workflow_id)
        if workflow is None:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        listing: ListingDraft | None = await uow.listing_drafts.get_by_workflow(workflow_id)
        listing_title = listing.title if listing else workflow.name
        listing_version = listing.version if listing else 1

        # Fetch all workflow assets
        assets = await uow.assets.list_for_workflow(workflow_id)

        # 1. Resolve Master PNG
        master_asset = await get_production_master_asset(uow, workflow_id)
        if master_asset is None:
            # Fallback to any master PNG or latest PNG asset
            master_asset = next(
                (a for a in assets if a.mime_type == "image/png" and (a.width or 0) >= 4000),
                None,
            )
        if master_asset is None:
            # Fallback to newest artwork candidate asset
            master_asset = next(
                (a for a in assets if a.mime_type == "image/png" and "/mockups/" not in a.storage_key and not a.storage_key.endswith(".zip")),
                None,
            )
        if master_asset is None:
            raise EntityNotFoundError("Master PNG Asset", workflow_id)

        logger.info("building_customer_package", workflow_id=str(workflow_id), master_id=str(master_asset.id), include_mockups=include_mockups)
        master_bytes = await self._storage.get(master_asset.storage_key)

        files_to_zip: dict[str, bytes] = {}

        # Master PNG
        files_to_zip["master.png"] = master_bytes

        # Print-ready PDF (include only if master raster is small enough to keep ZIP under Etsy 20MB limit)
        if len(master_bytes) < 10 * 1024 * 1024:
            try:
                pdf_bytes = create_print_ready_pdf(
                    master_bytes,
                    width_px=master_asset.width or 4500,
                    height_px=master_asset.height or 5400,
                )
                files_to_zip["print-ready.pdf"] = pdf_bytes
            except Exception as exc:
                logger.warning("pdf_generation_failed", error=str(exc))

        # Mockups (only for general downloads if requested, never for Etsy buyer delivery)
        if include_mockups:
            active_mockups = filter_active_user_mockups(assets, master_asset.id)
            for idx, mockup_asset in enumerate(active_mockups[:5], start=1):
                try:
                    mockup_bytes = await self._storage.get(mockup_asset.storage_key)
                    raw_prod = mockup_asset.provenance.get("product_type", f"preview-{idx}")
                    clean_prod = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw_prod))
                    files_to_zip[f"mockup-{idx}-{clean_prod}.png"] = mockup_bytes
                except Exception as exc:
                    logger.warning("mockup_fetch_failed", asset_id=str(mockup_asset.id), error=str(exc))

        # License and Instructions text
        owner_settings = None
        if hasattr(uow, "owner_settings") and uow.owner_settings and hasattr(workflow, "owner_id") and workflow.owner_id:
            try:
                import inspect
                res = uow.owner_settings.get_for_user(workflow.owner_id)
                if inspect.isawaitable(res):
                    owner_settings = await res
                elif hasattr(res, "shop_name"):
                    owner_settings = res
            except Exception:
                owner_settings = None

        shop_name = getattr(owner_settings, "shop_name", "Digital Art Studio") if owner_settings else "Digital Art Studio"

        license_doc = generate_license_text(shop_name, listing_title)
        instructions_doc = generate_instructions_text(listing_title)

        files_to_zip["LICENSE.txt"] = license_doc.encode("utf-8")
        files_to_zip["INSTRUCTIONS.txt"] = instructions_doc.encode("utf-8")

        # Checksum manifest
        manifest_text = generate_checksum_manifest(files_to_zip)
        files_to_zip["manifest.sha256"] = manifest_text.encode("utf-8")

        # Build ZIP
        zip_bytes = build_zip_archive(files_to_zip)
        zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()
        package_prefix = "customer-package" if include_mockups else "etsy-delivery"
        storage_key = f"workflows/{workflow_id}/packages/{package_prefix}-v{listing_version}.zip"

        # Put to S3 / MinIO
        stored_obj = await self._storage.put(storage_key, zip_bytes, "application/zip")

        # Check if asset record exists for this sha256
        existing_asset = await uow.assets.get_by_checksum_sha256(workflow_id, zip_sha256)
        if existing_asset is not None:
            return existing_asset

        package_asset = Asset(
            workflow_id=workflow_id,
            storage_key=stored_obj.storage_key,
            mime_type="application/zip",
            byte_size=len(zip_bytes),
            checksum_sha256=zip_sha256,
            provenance={
                "kind": "customer_package" if include_mockups else "etsy_delivery_package",
                "version": listing_version,
                "file_count": len(files_to_zip),
                "has_pdf": "print-ready.pdf" in files_to_zip,
                "mockup_count": len(files_to_zip) - 4 if include_mockups else 0,
            },
        )
        await uow.assets.add(package_asset)

        # Update listing licence_text & customer_instructions if empty
        if listing is not None:
            await uow.listing_drafts.update(
                listing.id,
                licence_text=license_doc,
                customer_instructions=instructions_doc,
            )

        logger.info(
            "customer_package_assembled",
            workflow_id=str(workflow_id),
            asset_id=str(package_asset.id),
            size=len(zip_bytes),
        )
        return package_asset

    async def build_etsy_delivery_package(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> Asset:
        """Build customer delivery package strictly for Etsy without marketing mockups."""
        return await self.build_customer_package(workflow_id, uow, include_mockups=False)
