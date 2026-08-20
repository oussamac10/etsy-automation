"""Application service for assembling customer download ZIP packages."""

from __future__ import annotations

import hashlib
import re
import uuid
import structlog

from app.application.brand_resolver import resolve_connected_shop_name
from app.application.unit_of_work import UnitOfWork
from app.domain.errors import EntityNotFoundError
from app.domain.etsy_delivery_planner import (
    MAX_ETSY_DIGITAL_FILE_BYTES,
    MAX_ETSY_DIGITAL_FILES_COUNT,
    EtsyDigitalDeliveryPlanner,
)
from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
    optimize_png_deflate,
    sanitize_brand_slug,
    sanitize_product_title,
)
from app.domain.production_resolver import get_production_master_asset
from app.infrastructure.models import Asset, ListingDraft, ProductWorkflow
from app.ports.providers import ObjectStorage

logger = structlog.get_logger(__name__)


class CustomerPackageService:
    """Builds and stores deterministic customer ZIP packages identical to Etsy digital deliverables."""

    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    async def build_customer_package(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
        *,
        include_mockups: bool = False,
    ) -> Asset:
        """Assemble customer ZIP package identical to the upload package dispatched to Etsy."""
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

        logger.info("building_customer_package", workflow_id=str(workflow_id), master_id=str(master_asset.id))
        master_bytes = await self._storage.get(master_asset.storage_key)

        # Resolve dynamic connected Etsy shop name
        shop_name = await resolve_connected_shop_name(uow, workflow.owner_id)

        shop_slug = sanitize_brand_slug(shop_name, max_length=20)
        product_slug = sanitize_product_title(listing_title, max_length=25)
        base_prefix = f"{shop_slug}_{product_slug}"

        # 1. Optimize master PNG losslessly
        optimized_master = optimize_png_deflate(master_bytes)

        # 2. Build Documentation
        license_doc = generate_license_text(shop_name, listing_title).encode("utf-8")
        instructions_doc = generate_instructions_text(listing_title, shop_name=shop_name).encode("utf-8")

        # 3. Build Print-Ready PDF
        pdf_bytes = create_print_ready_pdf(
            optimized_master,
            width_px=master_asset.width or 4500,
            height_px=master_asset.height or 5400,
        )

        # 4. Assemble complete deliverables map
        pack_files: dict[str, bytes] = {
            f"{base_prefix}_PNG.png": optimized_master,
            f"{base_prefix}_LICENSE.txt": license_doc,
            f"{base_prefix}_INSTRUCTIONS.txt": instructions_doc,
        }
        if pdf_bytes is not None:
            pack_files[f"{base_prefix}_Print_Ready.pdf"] = pdf_bytes

        manifest = generate_checksum_manifest(pack_files).encode("utf-8")
        pack_files[f"{base_prefix}_manifest.sha256"] = manifest

        zip_bytes = build_zip_archive(pack_files)
        zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()
        zip_filename = f"{base_prefix}_Digital_Download.zip"
        storage_key = f"workflows/{workflow_id}/packages/{zip_filename}"

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
                "kind": "customer_package",
                "version": listing_version,
                "filename": zip_filename,
                "file_count": len(pack_files),
                "has_pdf": pdf_bytes is not None,
                "mockup_count": 0,
            },
        )
        await uow.assets.add(package_asset)

        # Update listing licence_text & customer_instructions
        if listing is not None:
            await uow.listing_drafts.update(
                listing.id,
                licence_text=license_doc.decode("utf-8"),
                customer_instructions=instructions_doc.decode("utf-8"),
            )

        logger.info(
            "customer_package_assembled",
            workflow_id=str(workflow_id),
            asset_id=str(package_asset.id),
            filename=zip_filename,
            size=len(zip_bytes),
        )
        return package_asset

    async def build_etsy_delivery_package(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> Asset:
        """Build customer delivery package strictly matching Etsy digital delivery."""
        return await self.build_customer_package(workflow_id, uow)
