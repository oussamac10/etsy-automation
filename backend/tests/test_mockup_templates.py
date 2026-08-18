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
