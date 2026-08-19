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
    generate_instructions_text,
    generate_license_text,
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

        planner = EtsyDigitalDeliveryPlanner(
            max_file_bytes=MAX_ETSY_DIGITAL_FILE_BYTES,
            max_files_count=MAX_ETSY_DIGITAL_FILES_COUNT,
        )
        planned_files = planner.plan_delivery(
            master_png_bytes=master_bytes,
            listing_title=listing_title,
            shop_name=shop_name,
            master_width=master_asset.width or 4500,
            master_height=master_asset.height or 5400,
            include_pdf=True,
        )

        # Primary customer delivery ZIP file
        zip_file = next((f for f in planned_files if f.mime_type == "application/zip"), planned_files[0])
        zip_bytes = zip_file.content
        zip_sha256 = zip_file.checksum_sha256
        storage_key = f"workflows/{workflow_id}/packages/{zip_file.filename}"

        # Put to S3 / MinIO
        stored_obj = await self._storage.put(storage_key, zip_bytes, zip_file.mime_type)

        # Check if asset record exists for this sha256
        existing_asset = await uow.assets.get_by_checksum_sha256(workflow_id, zip_sha256)
        if existing_asset is not None:
            return existing_asset

        package_asset = Asset(
            workflow_id=workflow_id,
            storage_key=stored_obj.storage_key,
            mime_type=zip_file.mime_type,
            byte_size=len(zip_bytes),
            checksum_sha256=zip_sha256,
            provenance={
                "kind": "customer_package",
                "version": listing_version,
                "filename": zip_file.filename,
                "file_count": len(planned_files),
                "has_pdf": True,
                "mockup_count": 0,
            },
        )
        await uow.assets.add(package_asset)

        # Update listing licence_text & customer_instructions
        license_doc = generate_license_text(shop_name, listing_title)
        instructions_doc = generate_instructions_text(listing_title, shop_name=shop_name)
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
            filename=zip_file.filename,
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
