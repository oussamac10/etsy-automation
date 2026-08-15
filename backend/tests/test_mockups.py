"""Unit tests for Phase 7 Printful realistic mockup generator and MockupJob tracking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from app.domain.enums import ProviderName
from app.domain.workflow import JobStatus
from app.infrastructure.mockup_catalog import (
    DEFAULT_SUPPORTED_PRODUCTS,
    get_product_config,
    get_requested_mockup_products,
    normalize_mockup_product,
)
from app.infrastructure.models import MockupJob
from app.infrastructure.providers.fake_mockup_provider import FakeMockupProvider
from app.infrastructure.providers.printful_mockup_provider import PrintfulMockupProvider
from app.infrastructure.repositories.mockup import SqlMockupJobRepository
from app.ports.errors import ProviderError, ProviderErrorKind


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
        assert normalize_mockup_product("unknown_item") is None

    def test_get_product_config(self) -> None:
        cfg = get_product_config("tshirt")
        assert cfg.product_id == 71
        assert 9575 in cfg.variant_ids
        assert cfg.placement == "front"

        cfg_sweat = get_product_config("sweatshirt")
        assert cfg_sweat.product_id == 145
        assert 5434 in cfg_sweat.variant_ids

        cfg_tote = get_product_config("tote_bag")
        assert cfg_tote.product_id == 378
        assert 10732 in cfg_tote.variant_ids

        cfg_mug = get_product_config("mug")
        assert cfg_mug.product_id == 19
        assert 1320 in cfg_mug.variant_ids

        with pytest.raises(ValueError):
            get_product_config("nonexistent_product")

    def test_get_requested_mockup_products_filtering(self) -> None:
        # None or empty returns all 4 defaults
        assert get_requested_mockup_products(None) == DEFAULT_SUPPORTED_PRODUCTS
        assert get_requested_mockup_products([]) == DEFAULT_SUPPORTED_PRODUCTS

        # Custom subset
        assert get_requested_mockup_products(["tee", "mug"]) == ["tshirt", "mug"]
        assert get_requested_mockup_products(["hoodie"]) == ["sweatshirt"]

        # Only unsupported items falls back to all defaults
        assert get_requested_mockup_products(["poster", "canvas"]) == DEFAULT_SUPPORTED_PRODUCTS


class TestMugPlacementGeometry:
    def test_mug_front_layout_places_design_inside_visible_zone(self) -> None:
        from app.infrastructure.mockup_catalog import get_product_config, validate_mug_placement_geometry

        cfg = get_product_config("mug")
        assert cfg.mug_placement is not None
        assert cfg.mug_placement.layout_mode == "front_focus"
        assert cfg.mug_placement.requires_wrap_canvas is True

        # Test with standard 4500x5400 portrait master design fixture
        qa_res, box = validate_mug_placement_geometry(4500, 5400, cfg.mug_placement)
        assert qa_res.passed is True
        assert qa_res.error_message is None
        assert qa_res.is_inside_visible_zone is True
        assert qa_res.is_scale_reasonable is True

        left, top, width, height = box
        # Validate that horizontal center matches target center (1350)
        center_x = left + width / 2
        center_y = top + height / 2
        assert abs(center_x - 1350) <= 5.0
        assert abs(center_y - 525) <= 5.0

        # Validate design does not wrap around side (stays inside 900..1800)
        assert left >= 900
        assert left + width <= 1800

        # Safe margins maintained
        assert top >= 50
        assert top + height <= 1000

    def test_apparel_and_tote_isolated_from_mug_placement(self) -> None:
        from app.infrastructure.mockup_catalog import get_product_config

        for p_type in ["tshirt", "sweatshirt", "tote_bag"]:
            cfg = get_product_config(p_type)
            assert cfg.mug_placement is None
            assert cfg.placement == "front"

    def test_mug_geometric_qa_rejects_severe_offset(self) -> None:
        from app.infrastructure.mockup_catalog import MugPlacementConfig, validate_mug_placement_geometry

        bad_cfg = MugPlacementConfig(horizontal_offset=800)  # Pushed into handle area
        qa_res, _ = validate_mug_placement_geometry(4500, 5400, bad_cfg)
        assert qa_res.passed is False
        assert qa_res.is_inside_visible_zone is False
        assert qa_res.error_message is not None


class TestFakeMockupProvider:
    @pytest.mark.asyncio
    async def test_fake_mockup_lifecycle(self) -> None:
        provider = FakeMockupProvider(pending_cycles=1)
        res = await provider.create_mockup_task("tshirt", "https://example.com/master.png")
        assert res.status == "pending"
        assert res.task_id.startswith("fake_task_")

        # First poll should still be pending
        poll1 = await provider.get_mockup_task(res.task_id)
        assert poll1.status == "pending"

        # Second poll completed
        poll2 = await provider.get_mockup_task(res.task_id)
        assert poll2.status == "completed"
        assert len(poll2.mockup_urls) == 1

        # Download mockup
        img_bytes = await provider.download_mockup(poll2.mockup_urls[0])
        assert len(img_bytes) > 0

    @pytest.mark.asyncio
    async def test_fake_mockup_simulated_failure(self) -> None:
        provider = FakeMockupProvider(failed_products={"mug"})
        res = await provider.create_mockup_task("mug", "https://example.com/master.png")
        poll = await provider.get_mockup_task(res.task_id)
        assert poll.status == "failed"
        assert "Simulated provider failure" in str(poll.error_message)


class TestPrintfulMockupProvider:
    @pytest.mark.asyncio
    async def test_create_task_and_poll_success(self) -> None:
        mock_transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "code": 200,
                    "result": {
                        "task_key": "pf_task_123",
                        "status": "completed",
                        "mockups": [{"mockup_url": "https://printful.test/mockup.jpg"}],
                    },
                },
            )
        )
        async with httpx.AsyncClient(transport=mock_transport) as client:
            provider = PrintfulMockupProvider(access_token="test_token", http_client=client)
            res = await provider.create_mockup_task("tshirt", "https://example.com/master.png")
            assert res.task_id == "pf_task_123"

            poll = await provider.get_mockup_task("pf_task_123")
            assert poll.status == "completed"
            assert poll.mockup_urls == ["https://printful.test/mockup.jpg"]

    @pytest.mark.asyncio
    async def test_auth_error_mapping(self) -> None:
        mock_transport = httpx.MockTransport(
            lambda req: httpx.Response(401, json={"code": 401, "result": "Unauthorized"})
        )
        async with httpx.AsyncClient(transport=mock_transport) as client:
            provider = PrintfulMockupProvider(access_token="bad_token", http_client=client)
            with pytest.raises(ProviderError) as exc_info:
                await provider.create_mockup_task("tshirt", "https://example.com/master.png")
            assert exc_info.value.kind == ProviderErrorKind.AUTHENTICATION

    @pytest.mark.asyncio
    async def test_store_id_header_included(self) -> None:
        captured_headers = {}

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal captured_headers
            captured_headers = dict(req.headers)
            return httpx.Response(
                200,
                json={"code": 200, "result": {"task_key": "pf_task_456", "status": "completed", "mockups": []}},
            )

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            provider = PrintfulMockupProvider(access_token="test_token", store_id="12345", http_client=client)
            await provider.create_mockup_task("tshirt", "https://example.com/master.png")
            assert captured_headers.get("x-pf-store-id") == "12345"

    @pytest.mark.asyncio
    async def test_store_id_auto_discovery(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if req.url.path == "/stores":
                return httpx.Response(200, json={"code": 200, "result": [{"id": 98765, "name": "Test Store"}]})
            if req.headers.get("x-pf-store-id") == "98765":
                return httpx.Response(
                    200,
                    json={"code": 200, "result": {"task_key": "pf_task_789", "status": "completed", "mockups": []}},
                )
            return httpx.Response(400, json={"code": 400, "result": "This endpoint requires store_id"})

        mock_transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            provider = PrintfulMockupProvider(access_token="test_token", http_client=client)
            res = await provider.create_mockup_task("tshirt", "https://example.com/master.png")
            assert res.task_id == "pf_task_789"


class TestMockupJobRepository:
    @pytest.mark.asyncio
    async def test_mockup_job_repository_crud(self) -> None:
        session = MagicMock()
        session.flush = AsyncMock()
        repo = SqlMockupJobRepository(session)

        job_id = uuid.uuid4()
        workflow_id = uuid.uuid4()
        prod_job_id = uuid.uuid4()
        master_asset_id = uuid.uuid4()

        job = MockupJob(
            id=job_id,
            workflow_id=workflow_id,
            production_job_id=prod_job_id,
            master_asset_id=master_asset_id,
            provider=ProviderName.PRINTFUL,
            product_type="tshirt",
            provider_product_id=71,
            variant_ids=[4012],
            placement="front",
            status=JobStatus.QUEUED,
            attempt_count=0,
        )

        # Add
        added = await repo.add(job)
        assert added.id == job_id
        session.add.assert_called_once_with(job)
        session.flush.assert_called_once()

        # Update
        session.get = AsyncMock(return_value=job)
        updated = await repo.update(
            job_id,
            status=JobStatus.SUCCEEDED,
            external_task_id="task_abc",
            result_mockup_url="https://test.url/m.jpg",
            completed_at=datetime.now(UTC),
        )
        assert updated.status == JobStatus.SUCCEEDED
        assert updated.external_task_id == "task_abc"
