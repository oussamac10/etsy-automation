import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.mockup_template_store import (
    CustomMockupPlacement,
    MockupTemplateStore,
)


@pytest.mark.asyncio
async def test_mockup_template_store_save_and_list() -> None:
    owner_id = uuid.uuid4()
    mock_storage = MagicMock()
    mock_storage._bucket_name = "test-bucket"
    mock_storage.put = AsyncMock()
    manifest_payload = (
        b'{"id":"tpl-123","name":"Test T-Shirt","product_type":"tshirt",'
        b'"storage_key":"mockup-templates/tshirt/tpl-123.jpg",'
        b'"placement":{"left_pct":0.3,"top_pct":0.3,"width_pct":0.4,"height_pct":0.4,'
        b'"angle_deg":0.0,"blend_mode":"multiply"},"created_at":"2026-08-15T00:00:00Z"}'
    )
    mock_storage.get = AsyncMock(return_value=manifest_payload)
    mock_storage.signed_url = AsyncMock(return_value="https://storage.local/signed-url.jpg")
    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = {
        "Contents": [{"Key": f"mockup-templates/{owner_id}/tshirt/tpl-123.json"}]
    }
    mock_storage._get_client.return_value = mock_client

    store = MockupTemplateStore(mock_storage)

    # 1. Save template
    item = await store.save_template(
        owner_id=owner_id,
        name="Test T-Shirt",
        product_type="tshirt",
        image_bytes=b"fake-image-bytes",
        content_type="image/jpeg",
        placement=CustomMockupPlacement(left_pct=0.3, top_pct=0.3, width_pct=0.4, height_pct=0.4),
    )

    assert item.name == "Test T-Shirt"
    assert item.product_type == "tshirt"
    assert mock_storage.put.call_count == 2  # image and json manifest

    # 2. List templates
    templates = await store.list_templates(owner_id=owner_id, product_type="tshirt")
    assert len(templates) == 1
    assert templates[0].id == "tpl-123"
    assert templates[0].placement.left_pct == 0.3


def test_placement_schema_blend_mode_normalization() -> None:
    from app.api.routes.mockup_templates import PlacementSchema

    # Valid blend modes preserved
    for mode in ["over", "multiply", "overlay", "soft-light", "screen", "darken", "lighten"]:
        schema = PlacementSchema(blend_mode=mode)
        assert schema.blend_mode == mode

    # Hyphenated / underscored variations normalized
    schema = PlacementSchema(blend_mode="soft_light")
    assert schema.blend_mode == "soft-light"

    schema = PlacementSchema(blend_mode="color_burn")
    assert schema.blend_mode == "color-burn"

    # Unknown blend modes safely fall back to "over"
    schema = PlacementSchema(blend_mode="invalid_xyz")
    assert schema.blend_mode == "over"


@pytest.mark.asyncio
async def test_mockup_template_store_multi_placement() -> None:
    owner_id = uuid.uuid4()
    mock_storage = MagicMock()
    mock_storage._bucket_name = "test-bucket"
    mock_storage.put = AsyncMock()
    manifest_payload = (
        b'{"id":"tpl-multi","name":"Sticker Sheet 4-Pack","product_type":"sticker",'
        b'"storage_key":"mockup-templates/sticker/tpl-multi.jpg",'
        b'"placement":{"left_pct":0.1,"top_pct":0.1,"width_pct":0.35,"height_pct":0.35,"angle_deg":-15.0,"blend_mode":"over"},'
        b'"placements":['
        b'  {"id":"p1","left_pct":0.1,"top_pct":0.1,"width_pct":0.35,"height_pct":0.35,"angle_deg":-15.0,"blend_mode":"over"},'
        b'  {"id":"p2","left_pct":0.55,"top_pct":0.1,"width_pct":0.35,"height_pct":0.35,"angle_deg":15.0,"blend_mode":"multiply"},'
        b'  {"id":"p3","left_pct":0.1,"top_pct":0.55,"width_pct":0.35,"height_pct":0.35,"angle_deg":45.0,"blend_mode":"overlay"}'
        b'],'
        b'"created_at":"2026-08-20T00:00:00Z"}'
    )
    mock_storage.get = AsyncMock(return_value=manifest_payload)
    mock_storage.signed_url = AsyncMock(return_value="https://storage.local/signed-url.jpg")
    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = {
        "Contents": [{"Key": f"mockup-templates/{owner_id}/sticker/tpl-multi.json"}]
    }
    mock_storage._get_client.return_value = mock_client

    store = MockupTemplateStore(mock_storage)

    # 1. Save with multi placements
    item = await store.save_template(
        owner_id=owner_id,
        name="Sticker Sheet 4-Pack",
        product_type="sticker",
        image_bytes=b"fake-image-bytes",
        content_type="image/jpeg",
        placements=[
            CustomMockupPlacement(id="p1", left_pct=0.1, top_pct=0.1, width_pct=0.35, height_pct=0.35, angle_deg=-15),
            CustomMockupPlacement(id="p2", left_pct=0.55, top_pct=0.1, width_pct=0.35, height_pct=0.35, angle_deg=15),
        ],
    )

    assert item.name == "Sticker Sheet 4-Pack"
    assert len(item.placements) == 2
    assert item.placement.left_pct == 0.1

    # 2. List templates
    templates = await store.list_templates(owner_id=owner_id, product_type="sticker")
    assert len(templates) == 1
    assert templates[0].id == "tpl-multi"
    assert len(templates[0].placements) == 3
    assert templates[0].placements[1].angle_deg == 15.0
    assert templates[0].placements[2].blend_mode == "overlay"

