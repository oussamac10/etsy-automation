"""Printful Mockup Generator API adapter.

Communicates with Printful's Mockup Generator endpoints to asynchronously render
realistic product mockups without creating store products, orders, or fulfillments.
"""

from __future__ import annotations

import asyncio
import httpx

from app.infrastructure.mockup_catalog import get_product_config
from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.mockup_provider import MockupProvider, MockupTaskResult


class PrintfulMockupProvider(MockupProvider):
    """Adapter for Printful's async Mockup Generator API."""

    def __init__(
        self,
        access_token: str,
        store_id: str | int | None = None,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.printful.com",
    ) -> None:
        self._access_token = access_token.strip()
        self._store_id = str(store_id).strip() if store_id else None
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")

    async def _resolve_headers(self, http: httpx.AsyncClient) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "User-Agent": "EtsyAutomation/1.0",
        }

        # If store_id was not explicitly configured, discover it via GET /stores
        if not self._store_id:
            try:
                resp = await http.get(f"{self._base_url}/stores", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    stores = data.get("result", [])
                    if stores and isinstance(stores, list):
                        # Prioritize native/manual store if available, else first store
                        chosen = next((s for s in stores if s.get("type") in ("native", "manual", "api")), stores[0])
                        if chosen and "id" in chosen:
                            self._store_id = str(chosen["id"])
            except Exception:
                pass

        if self._store_id:
            headers["X-PF-Store-Id"] = self._store_id

        return headers

    async def create_mockup_task(
        self,
        product_type: str,
        image_url: str,
        *,
        placement: str | None = None,
        format: str = "jpg",
    ) -> MockupTaskResult:
        """Submit a mockup generation task to Printful with rate-limit retry."""
        config = get_product_config(product_type)
        url = f"{self._base_url}/mockup-generator/create-task/{config.product_id}"

        target_placement = placement or config.placement
        payload = {
            "variant_ids": config.variant_ids,
            "format": format or config.format,
            "files": [
                {
                    "placement": target_placement,
                    "image_url": image_url,
                    "position": {
                        "area_width": config.area_width,
                        "area_height": config.area_height,
                        "width": config.pos_width,
                        "height": config.pos_height,
                        "top": config.pos_top,
                        "left": config.pos_left,
                    },
                }
            ],
        }

        max_retries = 8
        for attempt in range(max_retries):
            try:
                client = self._http_client or httpx.AsyncClient(timeout=25.0)
                async with client if self._http_client is None else _noop_context(client) as http:
                    headers = await self._resolve_headers(http)
                    response = await http.post(url, json=payload, headers=headers)

                if response.status_code == 429:
                    retry_after = 30.0
                    try:
                        import re
                        m = re.search(r"after\s+(\d+)\s+seconds", response.text, re.IGNORECASE)
                        if m:
                            retry_after = float(m.group(1)) + 2.0
                    except Exception:
                        pass
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    raise ProviderError(
                        kind=ProviderErrorKind.RATE_LIMITED,
                        provider="printful",
                        operation="create_mockup_task",
                        message="Printful rate limit exceeded",
                    )

                if response.status_code in (401, 403):
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider="printful",
                        operation="create_mockup_task",
                        message=f"Printful authentication failed: {response.text[:200]}",
                    )
                if response.status_code >= 500:
                    raise ProviderError(
                        kind=ProviderErrorKind.RETRYABLE,
                        provider="printful",
                        operation="create_mockup_task",
                        message=f"Printful server error ({response.status_code}): {response.text[:200]}",
                    )
                if response.status_code >= 400:
                    raise ProviderError(
                        kind=ProviderErrorKind.INVALID_REQUEST,
                        provider="printful",
                        operation="create_mockup_task",
                        message=f"Printful rejected request ({response.status_code}): {response.text[:200]}",
                    )

                data = response.json()
                result = data.get("result", {})
                task_key = result.get("task_key")
                if not task_key:
                    raise ProviderError(
                        kind=ProviderErrorKind.PERMANENT,
                        provider="printful",
                        operation="create_mockup_task",
                        message="Printful did not return a task_key in response",
                    )

                status = result.get("status", "pending")
                return MockupTaskResult(
                    task_id=task_key,
                    status=status,
                    mockup_urls=[],
                )

            except ProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider="printful",
                    operation="create_mockup_task",
                    message=f"Printful network/timeout error: {exc}",
                ) from exc
            except Exception as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.PERMANENT,
                    provider="printful",
                    operation="create_mockup_task",
                    message=f"Unexpected error calling Printful API: {exc}",
                ) from exc

        raise ProviderError(
            kind=ProviderErrorKind.RATE_LIMITED,
            provider="printful",
            operation="create_mockup_task",
            message="Printful task creation failed after max retries",
        )

    async def get_mockup_task(self, external_task_id: str) -> MockupTaskResult:
        """Poll task status from Printful."""
        url = f"{self._base_url}/mockup-generator/task"
        params = {"task_key": external_task_id}

        max_retries = 5
        for attempt in range(max_retries):
            try:
                client = self._http_client or httpx.AsyncClient(timeout=25.0)
                async with client if self._http_client is None else _noop_context(client) as http:
                    headers = await self._resolve_headers(http)
                    response = await http.get(url, params=params, headers=headers)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(4.0 * (attempt + 1))
                        continue
                    raise ProviderError(
                        kind=ProviderErrorKind.RATE_LIMITED,
                        provider="printful",
                        operation="get_mockup_task",
                        message="Printful rate limit exceeded",
                    )

                if response.status_code in (401, 403):
                    raise ProviderError(
                        kind=ProviderErrorKind.AUTHENTICATION,
                        provider="printful",
                        operation="get_mockup_task",
                        message=f"Printful authentication failed: {response.text[:200]}",
                    )
                if response.status_code >= 500:
                    raise ProviderError(
                        kind=ProviderErrorKind.RETRYABLE,
                        provider="printful",
                        operation="get_mockup_task",
                        message=f"Printful server error ({response.status_code}): {response.text[:200]}",
                    )
                if response.status_code >= 400:
                    raise ProviderError(
                        kind=ProviderErrorKind.INVALID_REQUEST,
                        provider="printful",
                        operation="get_mockup_task",
                        message=f"Printful rejected task poll ({response.status_code}): {response.text[:200]}",
                    )

                data = response.json()
                result = data.get("result", {})
                status = result.get("status", "pending")

                if status == "completed":
                    urls: list[str] = []
                    for m in result.get("mockups", []):
                        if "mockup_url" in m and m["mockup_url"]:
                            urls.append(m["mockup_url"])
                        for extra in m.get("extra", []):
                            if "url" in extra and extra["url"]:
                                urls.append(extra["url"])

                    return MockupTaskResult(
                        task_id=external_task_id,
                        status="completed",
                        mockup_urls=urls,
                    )
                elif status == "failed":
                    error_msg = result.get("error") or "Printful mockup generation failed"
                    return MockupTaskResult(
                        task_id=external_task_id,
                        status="failed",
                        mockup_urls=[],
                        error_message=str(error_msg),
                    )
                else:
                    return MockupTaskResult(
                        task_id=external_task_id,
                        status="pending",
                        mockup_urls=[],
                    )

            except ProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider="printful",
                    operation="get_mockup_task",
                    message=f"Printful network/timeout error during poll: {exc}",
                ) from exc
            except Exception as exc:
                raise ProviderError(
                    kind=ProviderErrorKind.PERMANENT,
                    provider="printful",
                    operation="get_mockup_task",
                    message=f"Unexpected error polling Printful task: {exc}",
                ) from exc

        raise ProviderError(
            kind=ProviderErrorKind.RATE_LIMITED,
            provider="printful",
            operation="get_mockup_task",
            message="Printful task poll failed after max retries",
        )

    async def download_mockup(self, mockup_url: str) -> bytes:
        """Download rendered image bytes from temporary mockup URL."""
        try:
            client = self._http_client or httpx.AsyncClient(timeout=30.0)
            async with client if self._http_client is None else _noop_context(client) as http:
                response = await http.get(mockup_url)

            if response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.PERMANENT,
                    provider="printful",
                    operation="download_mockup",
                    message=f"Failed to download mockup from provider ({response.status_code})",
                )
            return response.content

        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="printful",
                operation="download_mockup",
                message=f"Error downloading mockup: {exc}",
            ) from exc


class _noop_context:
    """Helper context manager when reusing an existing client."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass
