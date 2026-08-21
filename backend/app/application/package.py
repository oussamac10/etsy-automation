"""Application service for assembling customer download ZIP packages."""

from __future__ import annotations

from datetime import datetime
import hashlib
import re
from typing import Any
import uuid
import structlog

from app.application.brand_resolver import resolve_connected_shop_name
from app.application.unit_of_work import UnitOfWork
from app.domain.errors import EntityNotFoundError
from app.domain.artwork_variants import (
    VariantStatus,
    compute_variant_filename,
    is_valid_artwork_variant_asset,
    is_variant_outdated,
)
from app.domain.etsy_delivery_planner import (
    MAX_ETSY_DIGITAL_FILE_BYTES,
    MAX_ETSY_DIGITAL_FILES_COUNT,
    EtsyDigitalDeliveryPlanner,
    validate_zip_integrity,
)
from app.domain.package_builder import (
    build_zip_archive,
    create_print_ready_pdf,
    generate_checksum_manifest,
    generate_instructions_text,
    generate_license_text,
    generate_variant_aware_readme,
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
        force_rebuild: bool = False,
    ) -> Asset:
        """Assemble customer ZIP package containing approved master and explicitly selected approved variants."""
        workflow: ProductWorkflow | None = await uow.workflows.get(workflow_id)
        if workflow is None:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        # Check if an existing package is already up to date and can be reused
        if not force_rebuild:
            preview = await self.get_package_preview(workflow_id, uow)
            if not preview.get("needs_rebuild"):
                existing_pkg = preview.get("package_asset")
                if isinstance(existing_pkg, Asset):
                    logger.info(
                        "reusing_existing_customer_package",
                        workflow_id=str(workflow_id),
                        asset_id=str(existing_pkg.id),
                    )
                    return existing_pkg

        listing: ListingDraft | None = await uow.listing_drafts.get_by_workflow(workflow_id)
        listing_title = listing.title if listing else workflow.name
        listing_version = listing.version if listing else 1

        # Fetch all workflow assets
        assets = await uow.assets.list_for_workflow(workflow_id)

        # 1. Resolve Master PNG
        master_asset = await get_production_master_asset(uow, workflow_id)
        if master_asset is None:
            master_asset = next(
                (a for a in assets if a.mime_type == "image/png" and (a.width or 0) >= 4000),
                None,
            )
        if master_asset is None:
            master_asset = next(
                (
                    a
                    for a in assets
                    if a.mime_type == "image/png"
                    and "/mockups/" not in a.storage_key
                    and not a.storage_key.endswith(".zip")
                ),
                None,
            )
        if master_asset is None:
            raise EntityNotFoundError("Master PNG Asset", workflow_id)

        logger.info("building_customer_package", workflow_id=str(workflow_id), master_id=str(master_asset.id))
        master_bytes = await self._storage.get(master_asset.storage_key)
        if not master_bytes:
            raise EntityNotFoundError("Master PNG storage bytes", workflow_id)

        # Resolve dynamic connected Etsy shop name
        shop_name = await resolve_connected_shop_name(uow, workflow.owner_id)

        shop_slug = sanitize_brand_slug(shop_name, max_length=20)
        product_slug = sanitize_product_title(listing_title, max_length=25)
        base_prefix = f"{shop_slug}_{product_slug}"

        # 1. Optimize master PNG losslessly
        optimized_master = optimize_png_deflate(master_bytes)
        master_filename = f"{base_prefix}_Original.png"

        # 2. Collect ONLY approved and explicitly selected variants
        included_variant_meta: list[dict[str, Any]] = []
        variant_pack_files: dict[str, bytes] = {}

        for asset in assets:
            if is_valid_artwork_variant_asset(asset.provenance):
                p = asset.provenance or {}
                # Strict Gate: Variant must be approved AND explicitly marked for inclusion AND not outdated
                is_approved = p.get("variant_status") == VariantStatus.APPROVED.value
                is_selected = bool(p.get("include_in_buyer_package"))
                is_outdated = is_variant_outdated(asset, master_asset)

                if is_approved and is_selected and not is_outdated:
                    try:
                        var_bytes = await self._storage.get(asset.storage_key)
                        if var_bytes:
                            v_type_str = str(p.get("variant_type", "variant"))
                            c_color_str = str(p.get("custom_color")) if p.get("custom_color") is not None else None
                            var_filename = compute_variant_filename(
                                base_prefix,
                                v_type_str,
                                custom_color=c_color_str,
                            )
                            optimized_var = optimize_png_deflate(var_bytes)
                            variant_pack_files[var_filename] = optimized_var
                            included_variant_meta.append({
                                "type": v_type_str,
                                "title": p.get("title") or f"{v_type_str.replace('_', ' ').title()} Version",
                                "filename": var_filename,
                                "asset_id": str(asset.id),
                                "byte_size": len(optimized_var),
                                "custom_color": c_color_str,
                            })
                    except Exception as var_err:
                        logger.warning(
                            "package_builder_variant_skipped",
                            asset_id=str(asset.id),
                            error=str(var_err),
                        )

        # 3. Build Documentation & Dynamic README
        all_included_for_readme = [
            {"type": "original", "title": "Original Version", "filename": master_filename},
            *included_variant_meta,
        ]
        readme_doc = generate_variant_aware_readme(
            listing_title,
            shop_name=shop_name,
            included_variants=all_included_for_readme,
        ).encode("utf-8")
        license_doc = generate_license_text(shop_name, listing_title).encode("utf-8")

        # 4. Build Print-Ready PDF
        pdf_bytes = create_print_ready_pdf(
            optimized_master,
            width_px=master_asset.width or 4500,
            height_px=master_asset.height or 5400,
        )

        # 5. Assemble complete deliverables map
        pack_files: dict[str, bytes] = {
            master_filename: optimized_master,
            f"{base_prefix}_README.txt": readme_doc,
            f"{base_prefix}_LICENSE.txt": license_doc,
            **variant_pack_files,
        }
        if pdf_bytes is not None:
            pack_files[f"{base_prefix}_Print_Ready.pdf"] = pdf_bytes

        manifest_text = generate_checksum_manifest(pack_files).encode("utf-8")
        pack_files[f"{base_prefix}_manifest.sha256"] = manifest_text

        # 6. Build and validate ZIP archive
        zip_bytes = build_zip_archive(pack_files)
        validate_zip_integrity(zip_bytes, list(pack_files.keys()))

        zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()
        zip_filename = f"{base_prefix}_Digital_Download.zip"
        storage_key = f"workflows/{workflow_id}/packages/{zip_filename}"

        # 7. Put to S3 / MinIO
        stored_obj = await self._storage.put(storage_key, zip_bytes, "application/zip")

        # Structured package manifest
        manifest_payload = {
            "files": [
                {
                    "type": "original",
                    "asset_id": str(master_asset.id),
                    "filename": master_filename,
                    "byte_size": len(optimized_master),
                },
                *[
                    {
                        "type": v["type"],
                        "asset_id": v["asset_id"],
                        "filename": v["filename"],
                        "byte_size": v["byte_size"],
                    }
                    for v in included_variant_meta
                ],
            ],
            "readme": True,
            "license": True,
            "has_pdf": pdf_bytes is not None,
            "total_uncompressed_bytes": sum(len(b) for b in pack_files.values()),
            "total_archive_bytes": len(zip_bytes),
        }

        # Check if asset record exists for this sha256
        existing_asset = await uow.assets.get_by_checksum_sha256(workflow_id, zip_sha256)
        if existing_asset is not None:
            package_asset = existing_asset
        else:
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
                    "variant_count": len(included_variant_meta),
                    "mockup_count": 0,
                    "manifest": manifest_payload,
                },
            )
            await uow.assets.add(package_asset)

        # 8. Check if Etsy draft already completed -> mark out of sync for explicit user sync
        if listing is not None:
            etsy_props = dict(listing.etsy_properties or {})
            if listing.etsy_dispatch_status == "completed" or listing.etsy_listing_id:
                etsy_props["etsy_files_out_of_sync"] = True

            await uow.listing_drafts.update(
                listing.id,
                licence_text=license_doc.decode("utf-8"),
                customer_instructions=readme_doc.decode("utf-8"),
                etsy_properties=etsy_props,
            )

        logger.info(
            "customer_package_assembled",
            workflow_id=str(workflow_id),
            asset_id=str(package_asset.id),
            filename=zip_filename,
            size=len(zip_bytes),
            variants_included=len(included_variant_meta),
        )
        return package_asset

    async def get_package_preview(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> dict[str, Any]:
        """Compute buyer package preview, breakdown of files, and rebuild status."""
        workflow: ProductWorkflow | None = await uow.workflows.get(workflow_id)
        if workflow is None:
            raise EntityNotFoundError("ProductWorkflow", workflow_id)

        listing: ListingDraft | None = await uow.listing_drafts.get_by_workflow(workflow_id)
        listing_title = listing.title if listing else workflow.name

        assets = await uow.assets.list_for_workflow(workflow_id)
        master_asset = await get_production_master_asset(uow, workflow_id)
        if master_asset is None:
            master_asset = next(
                (a for a in assets if a.mime_type == "image/png" and (a.width or 0) >= 4000),
                None,
            )

        shop_name = await resolve_connected_shop_name(uow, workflow.owner_id)
        shop_slug = sanitize_brand_slug(shop_name, max_length=20)
        product_slug = sanitize_product_title(listing_title, max_length=25)
        base_prefix = f"{shop_slug}_{product_slug}"

        files_breakdown: list[dict[str, Any]] = []
        included_count = 0
        estimated_total_bytes = 0

        # 1. Master PNG
        if master_asset:
            m_size = master_asset.byte_size or 13 * 1024 * 1024
            files_breakdown.append({
                "type": "original",
                "name": "Original Master PNG",
                "filename": f"{base_prefix}_Original.png",
                "byte_size": m_size,
                "included": True,
                "status": "ready",
                "asset_id": str(master_asset.id),
            })
            included_count += 1
            estimated_total_bytes += m_size

        # 2. Variants
        variants = [a for a in assets if is_valid_artwork_variant_asset(a.provenance)]
        for v in variants:
            p = v.provenance or {}
            v_type = str(p.get("variant_type", "variant"))
            c_color = str(p.get("custom_color")) if p.get("custom_color") is not None else None
            v_title = str(p.get("title") or f"{v_type.replace('_', ' ').title()} Version")
            v_filename = compute_variant_filename(base_prefix, v_type, custom_color=c_color)
            is_approved = p.get("variant_status") == VariantStatus.APPROVED.value
            is_selected = bool(p.get("include_in_buyer_package"))
            is_outdated = is_variant_outdated(v, master_asset) if master_asset else False

            status_str = "ready"
            if not is_approved:
                status_str = "unapproved"
            elif is_outdated:
                status_str = "outdated"

            v_size = v.byte_size or 13 * 1024 * 1024
            is_inc = is_approved and is_selected and not is_outdated
            if is_inc:
                included_count += 1
                estimated_total_bytes += v_size

            files_breakdown.append({
                "type": v_type,
                "name": v_title,
                "filename": v_filename,
                "byte_size": v_size,
                "included": is_inc,
                "status": status_str,
                "asset_id": str(v.id),
            })

        # 3. Documentation
        files_breakdown.append({
            "type": "readme",
            "name": "Usage & Print Guide",
            "filename": f"{base_prefix}_README.txt",
            "byte_size": 2500,
            "included": True,
            "status": "ready",
            "asset_id": None,
        })
        files_breakdown.append({
            "type": "license",
            "name": "Commercial License",
            "filename": f"{base_prefix}_LICENSE.txt",
            "byte_size": 1800,
            "included": True,
            "status": "ready",
            "asset_id": None,
        })
        estimated_total_bytes += 4300

        def _created_at_key(x: Any) -> float:
            dt = getattr(x, "created_at", None)
            if dt is None:
                return 0.0
            return dt.timestamp() if hasattr(dt, "timestamp") else 0.0

        # Existing package asset
        package_asset = next(
            (
                a
                for a in sorted(assets, key=_created_at_key, reverse=True)
                if (a.provenance or {}).get("kind") == "customer_package"
            ),
            None,
        )

        needs_rebuild = True
        if package_asset and package_asset.provenance:
            pkg_manifest = package_asset.provenance.get("manifest")
            if pkg_manifest and isinstance(pkg_manifest, dict):
                pkg_files = pkg_manifest.get("files", [])
                pkg_asset_ids = {f.get("asset_id") for f in pkg_files if f.get("asset_id")}
                current_included_ids = {
                    f["asset_id"] for f in files_breakdown if f["included"] and f["asset_id"] is not None
                }
                if pkg_asset_ids == current_included_ids:
                    needs_rebuild = False

        etsy_props = (listing.etsy_properties if listing else None) or {}
        etsy_files_out_of_sync = bool(etsy_props.get("etsy_files_out_of_sync", False))

        return {
            "workflow_id": workflow_id,
            "files": files_breakdown,
            "included_count": included_count,
            "estimated_total_bytes": estimated_total_bytes,
            "needs_rebuild": needs_rebuild,
            "etsy_files_out_of_sync": etsy_files_out_of_sync,
            "package_asset": package_asset,
        }

    async def build_etsy_delivery_package(
        self,
        workflow_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> Asset:
        """Build customer delivery package strictly matching Etsy digital delivery."""
        return await self.build_customer_package(workflow_id, uow)

