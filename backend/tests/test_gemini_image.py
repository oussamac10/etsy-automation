import base64
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.ports.providers import ImageRequest
from app.providers.gemini import GeminiImageAdapter


@pytest.mark.asyncio
async def test_gemini_image_generate_success() -> None:
    adapter = GeminiImageAdapter(api_key="test-key", default_model="gemini-3.1-flash-image")

    fake_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-image-bytes").decode("utf-8")
    mock_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": fake_png_b64,
                            }
                        }
                    ]
                }
            }
        ]
    }

    req = ImageRequest(
        positive_prompt="A cozy autumn book reading illustration",
        negative_prompt="blurry, low quality",
        width=1024,
        height=1024,
        quality="high",
        idempotency_key="test-key-1",
        candidate_count=1,
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json = lambda: mock_response_data
        mock_post.return_value = mock_resp

        result = await adapter.generate(req)

        assert len(result.candidates) == 1
        assert result.image_bytes.startswith(b"\x89PNG")
        assert result.cost_usd == Decimal("0.020")
        assert result.model == "gemini-3.1-flash-image"

        # Verify sent payload
        call_kwargs = mock_post.call_args.kwargs
        json_body = call_kwargs["json"]
        parts = json_body["contents"][0]["parts"]
        assert len(parts) == 1
        assert "A cozy autumn book reading illustration" in parts[0]["text"]
        assert "Avoid: blurry, low quality" in parts[0]["text"]
        assert json_body["generationConfig"]["imageConfig"]["aspectRatio"] == "1:1"


@pytest.mark.asyncio
async def test_gemini_image_refine_with_reference_image() -> None:
    adapter = GeminiImageAdapter(api_key="test-key", default_model="gemini-3.1-flash-image")

    fake_png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nrefined-image").decode("utf-8")
    mock_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": fake_png_b64,
                            }
                        }
                    ]
                }
            }
        ]
    }

    ref_bytes = b"\x89PNG\r\n\x1a\nreference-original-bytes"
    req = ImageRequest(
        positive_prompt="Add warm orange autumn leaves in background",
        negative_prompt="",
        width=1024,
        height=1024,
        quality="high",
        idempotency_key="test-key-2",
        candidate_count=1,
        reference_image_bytes=ref_bytes,
        reference_image_mime_type="image/png",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json = lambda: mock_response_data
        mock_post.return_value = mock_resp

        result = await adapter.generate(req)

        assert len(result.candidates) == 1
        assert result.image_bytes.startswith(b"\x89PNG")

        call_kwargs = mock_post.call_args.kwargs
        json_body = call_kwargs["json"]
        parts = json_body["contents"][0]["parts"]
        assert len(parts) == 2
        assert "inlineData" in parts[0]
        assert parts[0]["inlineData"]["mimeType"] == "image/png"
        assert "Add warm orange autumn leaves in background" in parts[1]["text"]
        assert "plain clean background" in parts[1]["text"]
