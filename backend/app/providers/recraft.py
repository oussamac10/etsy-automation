from __future__ import annotations

from decimal import Decimal

import httpx

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import ImageCandidate, ImageRequest, ImageResponse


class RecraftImageAdapter:
    """Live Recraft V4.1 image-generation adapter.

    Communicates with the official Recraft API at https://external.api.recraft.ai/v1.
    Downloads the resulting images from the returned URLs to return raw bytes.
    """

    name = "recraft"

    def __init__(
        self,
        api_key: str,
        default_model: str = "recraftv4_1",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._timeout = timeout_seconds

    async def generate(self, request: ImageRequest) -> ImageResponse:
        model = request.model or self._default_model

        # Check if this is an image-to-image refinement request
        if request.reference_image_bytes is not None:
            endpoint = "https://external.api.recraft.ai/v1/images/imageToImage"
            headers = {
                "Authorization": f"Bearer {self._api_key}",
            }
            form_data = {
                "prompt": request.positive_prompt,
                "model": model,
                "strength": str(request.strength if request.strength is not None else 0.20),
                "n": str(request.candidate_count),
                "response_format": "url",
            }
            files = {
                "image": (
                    "reference.png",
                    request.reference_image_bytes,
                    request.reference_image_mime_type or "image/png",
                )
            }

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        data=form_data,
                        files=files,
                    )
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="refine",
                    message="Recraft API imageToImage request timed out.",
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="refine",
                    message=f"HTTP request error: {exc!s}",
                ) from exc
        else:
            endpoint = "https://external.api.recraft.ai/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            # Recraft size parameter accepts aspect ratios or dimensions (e.g. "1024x1024")
            size = request.aspect_ratio
            if not size:
                size = (
                    f"{request.width}x{request.height}"
                    if request.width and request.height
                    else "1024x1024"
                )

            payload: dict[str, object] = {
                "prompt": request.positive_prompt,
                "model": model,
                "size": size,
                "n": request.candidate_count,
                "response_format": "url",
            }

            if request.negative_prompt and "recraftv4" not in model.lower():
                payload["negative_prompt"] = request.negative_prompt

            # Handle transparent background outputs by requesting png output
            # Vector models natively support SVG/transparency
            if "vector" in model:
                payload["output_format"] = "svg"
            elif request.output_format:
                payload["output_format"] = request.output_format

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="generate",
                    message="Recraft API request timed out.",
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="generate",
                    message=f"HTTP request error: {exc!s}",
                ) from exc

        if response.status_code == 401:
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider=self.name,
                operation="generate",
                message="Invalid API Key or unauthorized request to Recraft.",
            )
        elif response.status_code == 429:
            raise ProviderError(
                kind=ProviderErrorKind.RATE_LIMITED,
                provider=self.name,
                operation="generate",
                message="Recraft API rate limit exceeded.",
            )
        elif response.status_code >= 500:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="generate",
                message=f"Recraft server error: {response.status_code}",
            )
        elif response.status_code >= 400:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=self.name,
                operation="generate",
                message=f"Recraft bad request: {response.text}",
            )

        data = response.json()
        results = data.get("data", [])
        if not results:
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider=self.name,
                operation="generate",
                message="Recraft API returned no image results.",
            )

        # Download every candidate image from the temporary URLs
        candidates: list[ImageCandidate] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for idx, item in enumerate(results):
                url = item.get("url")
                if not url:
                    continue
                img_resp = await client.get(url)
                if img_resp.status_code != 200:
                    msg = f"Failed to download candidate {idx}: HTTP {img_resp.status_code}"
                    raise ProviderError(
                        kind=ProviderErrorKind.RETRYABLE,
                        provider=self.name,
                        operation="download_image",
                        message=msg,
                    )

                content_type = img_resp.headers.get("content-type", "image/png")
                candidates.append(
                    ImageCandidate(
                        image_bytes=img_resp.content,
                        mime_type=content_type,
                        width=request.width,
                        height=request.height,
                    )
                )

        # Extract request ID if available in headers, or generate deterministic one
        provider_request_id = response.headers.get("x-request-id")

        # Calculate cost (in Decimal USD)
        # Standard: $0.035, Vector: $0.08, Pro: $0.21, V3 refinement: $0.040
        if "pro" in model:
            unit_price = Decimal("0.21")
        elif "vector" in model:
            unit_price = Decimal("0.08")
        elif "v3" in model:
            unit_price = Decimal("0.040")
        else:
            unit_price = Decimal("0.035")

        cost_usd = unit_price * request.candidate_count

        return ImageResponse(
            candidates=candidates,
            model=model,
            provider_request_id=provider_request_id,
            cost_usd=cost_usd,
        )
