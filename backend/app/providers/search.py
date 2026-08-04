from __future__ import annotations

import httpx
from datetime import UTC, datetime

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import SearchQuery, SearchResult


class TavilySearchAdapter:
    """Live Tavily Search API Adapter.

    Performs query research and extracts web evidence.
    """

    name = "tavily"

    def __init__(self, api_key: str, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        payload = {
            "api_key": self._api_key,
            "query": query.text,
            "search_depth": "basic",
            "max_results": 3,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json=payload,
                )

            if response.status_code == 401:
                raise ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    provider=self.name,
                    operation="search",
                    message="Invalid Tavily API Key.",
                )
            elif response.status_code == 429:
                raise ProviderError(
                    kind=ProviderErrorKind.RATE_LIMITED,
                    provider=self.name,
                    operation="search",
                    message="Tavily rate limit exceeded.",
                )
            elif response.status_code >= 500:
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider=self.name,
                    operation="search",
                    message=f"Tavily server error: {response.status_code}",
                )
            elif response.status_code >= 400:
                raise ProviderError(
                    kind=ProviderErrorKind.INVALID_REQUEST,
                    provider=self.name,
                    operation="search",
                    message=f"Tavily bad request: {response.text}",
                )

            data = response.json()
            results = data.get("results", [])
            captured = datetime.now(UTC)

            return [
                SearchResult(
                    url=item["url"],
                    title=item["title"],
                    observation=item["content"],
                    source_type="trends",
                    captured_at=captured,
                )
                for item in results
            ]

        except httpx.TimeoutException as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="search",
                message="Tavily request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider=self.name,
                operation="search",
                message=f"HTTP search request error: {exc}",
            ) from exc
