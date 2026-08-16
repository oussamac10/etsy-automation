from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.ports.providers import ImageRequest
from app.providers.recraft import RecraftImageAdapter
from app.settings import Settings


def test_recraft_settings_defaults(settings: Settings):
    assert settings.recraft_generation_model == "recraftv4_1"
    assert settings.recraft_refinement_model == "recraftv3"
    assert settings.recraft_refinement_strength == 0.20
    assert settings.gemini_refinement_model == "gemini-3.1-flash-image"


@pytest.mark.asyncio
async def test_recraft_generation_uses_recraftv4():
    adapter = RecraftImageAdapter(api_key="recraft-key-123", default_model="recraftv4_1")

    mock_resp_json = {
        "data": [
            {"url": "https://external.api.recraft.ai/images/cand1.png"},
            {"url": "https://external.api.recraft.ai/images/cand2.png"},
        ]
    }

    req = ImageRequest(
        positive_prompt="Cozy reading nook with autumn vibes",
        negative_prompt="blurry",
        width=1024,
        height=1024,
        quality="standard",
        idempotency_key="key-1",
        candidate_count=2,
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_post_resp = AsyncMock()
        mock_post_resp.status_code = 200
        mock_post_resp.headers = {"x-request-id": "req-1"}
        mock_post_resp.json = lambda: mock_resp_json
        mock_post.return_value = mock_post_resp

        mock_get_resp = AsyncMock()
        mock_get_resp.status_code = 200
        mock_get_resp.headers = {"content-type": "image/png"}
        mock_get_resp.content = b"\x89PNG\r\n\x1a\ncand-bytes"
        mock_get.return_value = mock_get_resp

        res = await adapter.generate(req)

        assert len(res.candidates) == 2
        assert res.model == "recraftv4_1"
        assert res.cost_usd == Decimal("0.070")  # 2 * 0.035

        # Verify POST was made to /images/generations with JSON payload
        call_args = mock_post.call_args
        assert call_args.args[0] == "https://external.api.recraft.ai/v1/images/generations"
        assert call_args.kwargs["json"]["model"] == "recraftv4_1"
        assert call_args.kwargs["json"]["n"] == 2


@pytest.mark.asyncio
async def test_recraft_refinement_uses_image_to_image_v3():
    adapter = RecraftImageAdapter(api_key="recraft-key-123", default_model="recraftv3")

    mock_resp_json = {
        "data": [
            {"url": "https://external.api.recraft.ai/images/refined1.png"},
            {"url": "https://external.api.recraft.ai/images/refined2.png"},
        ]
    }

    req = ImageRequest(
        positive_prompt="Add a small retro enamel pin near the books",
        negative_prompt="",
        width=1024,
        height=1024,
        quality="standard",
        idempotency_key="key-refine-1",
        candidate_count=2,
        model="recraftv3",
        strength=0.20,
        reference_image_bytes=b"\x89PNG\r\n\x1a\noriginal-reference",
        reference_image_mime_type="image/png",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_post_resp = AsyncMock()
        mock_post_resp.status_code = 200
        mock_post_resp.headers = {"x-request-id": "req-refine-1"}
        mock_post_resp.json = lambda: mock_resp_json
        mock_post.return_value = mock_post_resp

        mock_get_resp = AsyncMock()
        mock_get_resp.status_code = 200
        mock_get_resp.headers = {"content-type": "image/png"}
        mock_get_resp.content = b"\x89PNG\r\n\x1a\nrefined-bytes"
        mock_get.return_value = mock_get_resp

        res = await adapter.generate(req)

        assert len(res.candidates) == 2
        assert res.model == "recraftv3"
        assert res.cost_usd == Decimal("0.080")  # 2 * 0.040 for v3

        # Verify POST was made to /images/imageToImage with multipart form-data
        call_args = mock_post.call_args
        assert call_args.args[0] == "https://external.api.recraft.ai/v1/images/imageToImage"
        assert call_args.kwargs["data"]["model"] == "recraftv3"
        assert call_args.kwargs["data"]["strength"] == "0.2"
        assert call_args.kwargs["data"]["n"] == "2"
        assert "image" in call_args.kwargs["files"]
        assert call_args.kwargs["files"]["image"][1] == b"\x89PNG\r\n\x1a\noriginal-reference"
