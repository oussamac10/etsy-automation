"""USPTO Trademark Search API adapter.

Connects to the official USPTO Open Data Portal Trademark Search API:
Endpoint: https://api.uspto.gov/trademark/search/v1/cases

Uses API Key configured via encrypted provider credentials (USPTO_API_KEY).
Never logs API keys or exposes internal request headers.
"""

from __future__ import annotations

from typing import Any
import httpx
import structlog

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import TrademarkMatch, TrademarkSearchPort

logger = structlog.get_logger(__name__)

USPTO_API_BASE = "https://api.uspto.gov/trademark/search/v1"
DEFAULT_TIMEOUT_SECONDS = 15.0


class UsptoTrademarkAdapter(TrademarkSearchPort):
    """Live USPTO Trademark Data Gateway."""

    def __init__(
        self,
        api_key: str,
        base_url: str = USPTO_API_BASE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    async def search_trademark(self, phrase: str) -> list[TrademarkMatch]:
        """Search USPTO trademark records for a given phrase.

        Queries word marks and returns normalized matches.
        """
        trimmed = phrase.strip()
        if not trimmed:
            return []

        url = f"{self._base_url}/cases"
        headers = {
            "x-api-key": self._api_key,
            "X-API-KEY": self._api_key,
            "Accept": "application/json",
            "User-Agent": "EtsyPngAutomation/1.0",
        }
        params = {
            "q": f'"{trimmed}"',
            "start": 0,
            "rows": 20,
        }

        try:
            if self._client is not None:
                response = await self._client.get(url, headers=headers, params=params)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, headers=headers, params=params)

            if response.status_code in (401, 403):
                logger.error("uspto_auth_failed", status_code=response.status_code)
                raise ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    provider="uspto",
                    operation="search",
                    message="USPTO API key rejected or unauthorized.",
                )

            if response.status_code == 429:
                logger.warning("uspto_rate_limited", phrase=trimmed)
                raise ProviderError(
                    kind=ProviderErrorKind.RATE_LIMITED,
                    provider="uspto",
                    operation="search",
                    message="USPTO API rate limit exceeded.",
                )

            if response.status_code == 404:
                return []

            if response.status_code >= 500:
                logger.error("uspto_server_error", status_code=response.status_code)
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider="uspto",
                    operation="search",
                    message=f"USPTO service error (status {response.status_code}).",
                )

            if response.status_code != 200:
                logger.warning(
                    "uspto_unexpected_status",
                    status_code=response.status_code,
                    phrase=trimmed,
                )
                return []

            try:
                data = response.json()
            except Exception as json_err:
                logger.error("uspto_malformed_json", error=str(json_err))
                raise ProviderError(
                    kind=ProviderErrorKind.PERMANENT,
                    provider="uspto",
                    operation="search",
                    message="USPTO returned malformed or non-JSON response.",
                ) from json_err

            return self._parse_uspto_response(data)

        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("uspto_timeout", phrase=trimmed)
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="uspto",
                operation="search",
                message=f"USPTO request timed out for phrase: {trimmed}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("uspto_request_failed", error=str(exc), phrase=trimmed)
            raise ProviderError(
                kind=ProviderErrorKind.PERMANENT,
                provider="uspto",
                operation="search",
                message=f"USPTO network request failed: {exc}",
            ) from exc

    def _parse_uspto_response(self, data: dict[str, Any]) -> list[TrademarkMatch]:
        """Normalize raw USPTO JSON into internal TrademarkMatch structures."""
        matches: list[TrademarkMatch] = []
        cases = data.get("cases", []) or data.get("results", []) or []

        for case in cases:
            mark_text = (
                case.get("markLiteralText")
                or case.get("wordMark")
                or case.get("markText")
                or ""
            ).strip()

            if not mark_text:
                continue

            serial_number = case.get("serialNumber") or case.get("caseSerialNumber")
            reg_number = case.get("registrationNumber")
            status_text = case.get("statusDescriptionText") or case.get("status") or "UNKNOWN"
            live_indicator = case.get("liveDeadIndicator") or case.get("statusCategory") or ""

            is_live = (
                live_indicator.upper() == "LIVE"
                or "LIVE" in status_text.upper()
                or not ("DEAD" in status_text.upper() or "CANCELLED" in status_text.upper())
            )

            # Class codes
            classes: list[str] = []
            raw_classes = case.get("internationalClassCodes") or case.get("classes") or []
            if isinstance(raw_classes, list):
                for cls in raw_classes:
                    cls_str = str(cls).strip()
                    if cls_str:
                        classes.append(cls_str.zfill(3))
            elif isinstance(raw_classes, str):
                classes = [c.strip().zfill(3) for c in raw_classes.split(",") if c.strip()]

            # Goods & Services
            goods_services = (
                case.get("goodsAndServicesDescriptionText")
                or case.get("goodsAndServices")
                or case.get("description")
            )

            # Owner
            owner = case.get("ownerName") or case.get("applicantName") or case.get("owner")
            filing_date = case.get("filingDate")
            reg_date = case.get("registrationDate")
            source_url = (
                f"https://tsdr.uspto.gov/#caseNumber={serial_number}&caseType=SERIAL_NO&searchType=statusSearch"
                if serial_number
                else None
            )

            matches.append(
                TrademarkMatch(
                    mark_text=mark_text,
                    serial_number=str(serial_number) if serial_number else None,
                    registration_number=str(reg_number) if reg_number else None,
                    status=status_text,
                    is_live=is_live,
                    goods_services=goods_services,
                    classes=classes,
                    owner=owner,
                    filing_date=filing_date,
                    registration_date=reg_date,
                    source_url=source_url,
                )
            )

        return matches
