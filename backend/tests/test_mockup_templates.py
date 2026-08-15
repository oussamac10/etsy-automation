from unittest.mock import AsyncMock, MagicMock
import pytest
from app.infrastructure.mockup_template_store import (
    CustomMockupPlacement,
    MockupTemplateStore,
)


@pytest.mark.asyncio
async def test_mockup_template_store_save_and_list():
    mock_storage = MagicMock()
    mock_storage._bucket_name = "test-bucket"
    mock_storage.put = AsyncMock()
    mock_storage.get = AsyncMock(return_value=b'{"id":"tpl-123","name":"Test T-Shirt","product_type":"tshirt","storage_key":"mockup_templates/tshirt/tpl-123.jpg","placement":{"left_pct":0.3,"top_pct":0.3,"width_pct":0.4,"height_pct":0.4,"angle_deg":0.0,"blend_mode":"multiply"},"created_at":"2026-08-15T00:00:00Z"}')
    mock_storage.signed_url = AsyncMock(return_value="https://storage.local/signed-url.jpg")
    mock_client = MagicMock()
    mock_client.list_objects_v2.return_value = {
        "Contents": [{"Key": "mockup_templates/tshirt/tpl-123.json"}]
    }
    mock_storage._get_client.return_value = mock_client

    store = MockupTemplateStore(mock_storage)

    # 1. Save template
    item = await store.save_template(
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
    templates = await store.list_templates("tshirt")
    assert len(templates) == 1
    assert templates[0].id == "tpl-123"
    assert templates[0].placement.left_pct == 0.3
