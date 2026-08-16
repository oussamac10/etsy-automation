"""Unit tests for Phase 7 user-uploaded custom mockup templates and multi-mockup pipeline."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.infrastructure.mockup_catalog import (
    DEFAULT_SUPPORTED_PRODUCTS,
    PRODUCT_PRESETS,
    get_product_preset,
    get_requested_mockup_products,
    normalize_mockup_product,
)
from app.infrastructure.mockup_template_store import (
    CustomMockupPlacement,
    MockupTemplateItem,
    MockupTemplateStore,
)
from app.api.routes.mockup_templates import (
    validate_image_payload,
    PlacementSchema,
    UploadTemplateRequest,
    CompositeCustomMockupRequest,
    composite_custom_mockup_endpoint,
)
from app.api.routes.workflows import (
    set_mockup_cover_endpoint,
    reorder_mockups_endpoint,
    delete_mockup_endpoint,
    to_production_job_response,
)
from app.api.schemas import ReorderMockupsRequest
from app.infrastructure.models import Asset, ProductionJob, ProductWorkflow


class TestMockupCatalog:
    def test_normalize_mockup_product_aliases(self) -> None:
        assert normalize_mockup_product("tshirt") == "tshirt"
        assert normalize_mockup_product("t-shirt") == "tshirt"
        assert normalize_mockup_product("T-Shirt") == "tshirt"
        assert normalize_mockup_product("tee") == "tshirt"
        assert normalize_mockup_product("hoodie") == "sweatshirt"
        assert normalize_mockup_product("sweater") == "sweatshirt"
        assert normalize_mockup_product("tote") == "tote_bag"
        assert normalize_mockup_product("tote-bag") == "tote_bag"
        assert normalize_mockup_product("coffee mug") == "mug"
        assert normalize_mockup_product("tumbler") == "tumbler"
        assert normalize_mockup_product("poster") == "poster"
        assert normalize_mockup_product("unknown_item") is None

    def test_get_product_preset(self) -> None:
        tshirt_preset = get_product_preset("tshirt")
        assert tshirt_preset.product_type == "tshirt"
        assert tshirt_preset.default_blend_mode == "multiply"
        assert 0.0 < tshirt_preset.default_left_pct < 1.0

        mug_preset = get_product_preset("mug")
        assert mug_preset.product_type == "mug"
        assert mug_preset.default_blend_mode == "over"

    def test_get_requested_mockup_products_filtering(self) -> None:
        assert get_requested_mockup_products(None) == DEFAULT_SUPPORTED_PRODUCTS
        assert get_requested_mockup_products([]) == DEFAULT_SUPPORTED_PRODUCTS
        assert get_requested_mockup_products(["tee", "mug"]) == ["tshirt", "mug"]
        assert get_requested_mockup_products(["hoodie"]) == ["sweatshirt"]
        assert get_requested_mockup_products(["unknown_xyz"]) == DEFAULT_SUPPORTED_PRODUCTS


class TestImagePayloadValidation:
    def test_valid_jpeg_and_png(self) -> None:
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 30
        validate_image_payload(jpeg_bytes, "image/jpeg")

        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 30
        validate_image_payload(png_bytes, "image/png")

    def test_reject_invalid_mime_type(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_image_payload(b"some content", "application/pdf")
        assert exc_info.value.status_code == 400
        assert "Unsupported image type" in exc_info.value.detail

    def test_reject_corrupt_or_truncated_image(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_image_payload(b"not an image", "image/jpeg")
        assert exc_info.value.status_code == 400

    def test_reject_oversized_payload(self) -> None:
        jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 200
        with pytest.raises(HTTPException) as exc_info:
            validate_image_payload(jpeg_header, "image/jpeg", max_bytes=100)
        assert exc_info.value.status_code == 400
        assert "exceeds" in exc_info.value.detail


class TestMockupTemplateStore:
    @pytest.mark.asyncio
    async def test_save_and_get_template_owner_scoped(self) -> None:
        storage = MagicMock()
        storage.put = AsyncMock()
        storage.signed_url = AsyncMock(return_value="https://storage.test/template.jpg")
        store = MockupTemplateStore(storage)

        owner_1 = uuid.uuid4()
        image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50

        saved = await store.save_template(
            owner_id=owner_1,
            name="My Studio Mug",
            product_type="mug",
            image_bytes=image_bytes,
            content_type="image/jpeg",
            placement=CustomMockupPlacement(left_pct=0.30, top_pct=0.30, width_pct=0.40, height_pct=0.40, blend_mode="over"),
        )

        assert saved.id is not None
        assert saved.name == "My Studio Mug"
        assert saved.product_type == "mug"
        assert saved.placement.blend_mode == "over"
        assert str(owner_1) in saved.storage_key
        assert f"mockup-templates/{owner_1}/mug/" in saved.storage_key
        assert storage.put.call_count == 2

    @pytest.mark.asyncio
    async def test_list_templates_owner_isolation(self) -> None:
        storage = MagicMock()
        storage._bucket_name = "test-bucket"
        storage.signed_url = AsyncMock(return_value="https://storage.test/signed.jpg")

        owner_a = uuid.uuid4()
        owner_b = uuid.uuid4()

        mock_s3_client = MagicMock()
        json_key_a = f"mockup-templates/{owner_a}/tshirt/template-123.json"
        manifest_a = {
            "id": "template-123",
            "owner_id": str(owner_a),
            "name": "Owner A T-Shirt",
            "product_type": "tshirt",
            "storage_key": f"mockup-templates/{owner_a}/tshirt/template-123.jpg",
            "placement": {"left_pct": 0.28, "top_pct": 0.25, "width_pct": 0.44, "height_pct": 0.48, "angle_deg": 0.0, "blend_mode": "multiply"},
            "created_at": "2026-08-16T10:00:00Z",
        }

        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [{"Key": json_key_a}],
        }
        storage._get_client = MagicMock(return_value=mock_s3_client)
        storage.get = AsyncMock(return_value=json.dumps(manifest_a).encode("utf-8"))

        store = MockupTemplateStore(storage)
        templates_a = await store.list_templates(owner_id=owner_a)

        assert len(templates_a) == 1
        assert templates_a[0].id == "template-123"
        assert templates_a[0].name == "Owner A T-Shirt"
        assert templates_a[0].owner_id == str(owner_a)

        mock_s3_client.list_objects_v2.return_value = {"Contents": []}
        templates_b = await store.list_templates(owner_id=owner_b)
        assert len(templates_b) == 0


class TestMultiMockupEndpoints:
    @pytest.fixture
    def mock_env(self):
        owner_id = uuid.uuid4()
        workflow_id = uuid.uuid4()
        master_asset_id = uuid.uuid4()

        user = MagicMock()
        user.id = owner_id
        user.email = "test@example.com"

        workflow = ProductWorkflow(
            id=workflow_id,
            owner_id=owner_id,
            state="PRODUCTION",
            version=1,
            idea_mode="hybrid",
        )

        master_asset = Asset(
            id=master_asset_id,
            workflow_id=workflow_id,
            artwork_job_id=None,
            derived_from_id=None,
            storage_key=f"production/{workflow_id}/master.png",
            mime_type="image/png",
            byte_size=1000,
            checksum_sha256="sha-master",
            provenance={"profile": "etsy-png-standard"},
        )

        storage = MagicMock()
        storage.get = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        storage.put = AsyncMock()
        storage.delete = AsyncMock()
        storage.signed_url = AsyncMock(side_effect=lambda key, *args, **kwargs: f"https://s3.test/{key}")

        settings = MagicMock()
        settings.image_max_input_bytes = 40 * 1024 * 1024
        settings.image_worker_url = "http://image-worker:8100"

        uow = MagicMock()
        uow.workflows.get = AsyncMock(return_value=workflow)
        uow.production_jobs.list_for_workflow = AsyncMock(return_value=[])
        uow.assets.get = AsyncMock(return_value=master_asset)

        assets_db: list[Asset] = [master_asset]

        async def _list_for_wf(wid):
            return [a for a in assets_db if a.workflow_id == wid]

        async def _add_asset(a):
            assets_db.append(a)
            return a

        async def _delete_asset(a):
            if a in assets_db:
                assets_db.remove(a)

        uow.assets.list_for_workflow = AsyncMock(side_effect=_list_for_wf)
        uow.assets.add = AsyncMock(side_effect=_add_asset)
        uow.assets.delete = AsyncMock(side_effect=_delete_asset)
        uow.session.flush = AsyncMock()
        uow.session.commit = AsyncMock()
        uow.commit = AsyncMock()

        return {
            "owner_id": owner_id,
            "workflow_id": workflow_id,
            "master_asset_id": master_asset_id,
            "user": user,
            "workflow": workflow,
            "master_asset": master_asset,
            "storage": storage,
            "settings": settings,
            "uow": uow,
            "assets_db": assets_db,
        }

    @pytest.mark.asyncio
    async def test_multiple_mockups_same_product_and_cover(self, mock_env) -> None:
        user = mock_env["user"]
        uow = mock_env["uow"]
        storage = mock_env["storage"]
        settings = mock_env["settings"]
        wf_id = mock_env["workflow_id"]
        assets_db = mock_env["assets_db"]

        mock_image_worker_response = {
            "mockup_base64": base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 40).decode("utf-8"),
            "width": 1200,
            "height": 1200,
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_image_worker_response
            mock_post.return_value = mock_resp

            # 1. Create first T-Shirt mockup: Black Flatlay
            req1 = CompositeCustomMockupRequest(
                workflow_id=wf_id,
                product_type="tshirt",
                template_image_base64=base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 30).decode("utf-8"),
                template_name="Black Bella Canvas Flatlay",
            )
            res1 = await composite_custom_mockup_endpoint(req1, user, uow, storage, settings)
            assert res1.product_type == "tshirt"
            assert res1.template_name == "Black Bella Canvas Flatlay"
            assert res1.is_cover is True  # First mockup becomes cover
            assert res1.listing_order == 1

            # 2. Create second T-Shirt mockup: White Flatlay (MUST NOT OVERWRITE FIRST)
            req2 = CompositeCustomMockupRequest(
                workflow_id=wf_id,
                product_type="tshirt",
                template_image_base64=base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 30).decode("utf-8"),
                template_name="White Bella Canvas Flatlay",
            )
            res2 = await composite_custom_mockup_endpoint(req2, user, uow, storage, settings)
            assert res2.asset_id != res1.asset_id
            assert res2.listing_order == 2
            assert res2.is_cover is False

            # Verify both T-shirt mockups exist in DB
            tshirt_mockups = [a for a in assets_db if a.provenance and a.provenance.get("product_type") == "tshirt"]
            assert len(tshirt_mockups) == 2
            assert tshirt_mockups[0].id == res1.asset_id
            assert tshirt_mockups[1].id == res2.asset_id
            assert tshirt_mockups[0].derived_from_id == mock_env["master_asset_id"]
            assert tshirt_mockups[1].derived_from_id == mock_env["master_asset_id"]

            # 3. Create third T-Shirt mockup: Female Model
            req3 = CompositeCustomMockupRequest(
                workflow_id=wf_id,
                product_type="tshirt",
                template_image_base64=base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 30).decode("utf-8"),
                template_name="Female Model Black",
            )
            res3 = await composite_custom_mockup_endpoint(req3, user, uow, storage, settings)
            assert len([a for a in assets_db if a.provenance and a.provenance.get("product_type") == "tshirt"]) == 3

            # 4. Create Mug mockup (isolated under mug)
            req_mug = CompositeCustomMockupRequest(
                workflow_id=wf_id,
                product_type="mug",
                template_image_base64=base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 30).decode("utf-8"),
                template_name="Kitchen Scene Mug",
            )
            res_mug = await composite_custom_mockup_endpoint(req_mug, user, uow, storage, settings)
            mug_mockups = [a for a in assets_db if a.provenance and a.provenance.get("product_type") == "mug"]
            assert len(mug_mockups) == 1
            assert mug_mockups[0].id == res_mug.asset_id

            # 5. Test Set as Cover: elect res2 as cover
            cover_res = await set_mockup_cover_endpoint(wf_id, res2.asset_id, user, uow, storage)
            assert cover_res.id == res2.asset_id
            assert cover_res.provenance.get("is_cover") is True

            # Verify res1 is no longer cover
            a1 = next(a for a in assets_db if a.id == res1.asset_id)
            assert a1.provenance.get("is_cover") is False

            # 6. Test Reorder Mockups
            new_order = [res3.asset_id, res1.asset_id, res2.asset_id, res_mug.asset_id]
            reorder_req = ReorderMockupsRequest(asset_ids=new_order)
            reordered = await reorder_mockups_endpoint(wf_id, reorder_req, user, uow, storage)
            assert len(reordered) == 4
            # Cover is res2 so it will be first in sorted_mockups, but listing_order is set correctly
            a3 = next(a for a in assets_db if a.id == res3.asset_id)
            assert a3.provenance.get("listing_order") == 1

            # 7. Test to_production_job_response
            job = ProductionJob(
                id=uuid.uuid4(),
                workflow_id=wf_id,
                source_asset_id=None,
                output_asset_id=mock_env["master_asset_id"],
                operations=["trim", "upscale", "typography"],
                status="SUCCEEDED",
                idempotency_key="job-123",
                attempt_count=1,
            )
            prod_resp = await to_production_job_response(job, storage, uow)
            assert len(prod_resp.mockup_assets) == 4
            assert "tshirt" in prod_resp.mockup_urls
            assert "mug" in prod_resp.mockup_urls

            # 8. Test Delete Mockup: delete res3
            del_resp = await delete_mockup_endpoint(wf_id, res3.asset_id, user, uow, storage)
            assert del_resp.status_code == 204
            assert storage.delete.called
            assert not any(a.id == res3.asset_id for a in assets_db)
            # Master PNG and other mockups remain intact
            assert any(a.id == mock_env["master_asset_id"] for a in assets_db)
            assert len([a for a in assets_db if a.provenance and a.provenance.get("product_type") == "tshirt"]) == 2
