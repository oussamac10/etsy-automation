"""USPTO TSDR (Trademark Status & Document Retrieval) verification adapter."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.ports.errors import ProviderError, ProviderErrorKind

logger = structlog.get_logger(__name__)


class UsptoTsdrAdapter:
    """Queries the official USPTO TSDR API to verify candidate case status by serial number."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://tsdrapi.uspto.gov/ts/cd/casestatus",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def verify_serial_number(self, serial_number: str) -> dict[str, Any] | None:
        """Fetch fresh trademark case status for a serial number from TSDR."""
        clean_serial = serial_number.strip().replace(" ", "").replace("-", "")
        if not clean_serial or not clean_serial.isalnum():
            return None

        url = f"{self._base_url}/sn{clean_serial}/info.json"
        headers = {
            "Accept": "application/json",
            "User-Agent": "EtsyAutomation-TSDR/1.0",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
            headers["USPTO-API-KEY"] = self._api_key

        try:
            if self._client:
                response = await self._client.get(url, headers=headers, timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url, headers=headers)

            if response.status_code == 404:
                return None

            if response.status_code in (401, 403):
                logger.warning(
                    "tsdr_auth_failed", status_code=response.status_code, serial=clean_serial
                )
                raise ProviderError(
                    kind=ProviderErrorKind.AUTHENTICATION,
                    provider="tsdr",
                    operation="verify_serial_number",
                    message=f"TSDR authentication or entitlement failed: HTTP {response.status_code}",
                )

            if response.status_code == 429:
                logger.warning("tsdr_rate_limited", serial=clean_serial)
                raise ProviderError(
                    kind=ProviderErrorKind.RATE_LIMITED,
                    provider="tsdr",
                    operation="verify_serial_number",
                    message="TSDR rate limit exceeded.",
                )

            if response.status_code >= 500:
                logger.warning(
                    "tsdr_server_error", status_code=response.status_code, serial=clean_serial
                )
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider="tsdr",
                    operation="verify_serial_number",
                    message=f"TSDR server error: HTTP {response.status_code}",
                )

            response.raise_for_status()
            data = response.json()
            return self._parse_tsdr_response(data, clean_serial)

        except (ProviderError, httpx.HTTPStatusError):
            raise
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as exc:
            logger.warning("tsdr_timeout", serial=clean_serial, error=str(exc))
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="tsdr",
                operation="verify_serial_number",
                message=f"TSDR request timed out: {exc}",
            ) from exc
        except Exception as exc:
            logger.warning("tsdr_unexpected_error", serial=clean_serial, error=str(exc))
            raise ProviderError(
                kind=ProviderErrorKind.PERMANENT,
                provider="tsdr",
                operation="verify_serial_number",
                message=f"TSDR query failed: {exc}",
            ) from exc

    def _parse_tsdr_response(self, data: dict[str, Any], serial_number: str) -> dict[str, Any]:
        """Parse structured TSDR response JSON."""
        status_text = "REGISTERED"
        is_live = True
        classes: list[str] = []
        goods_services = None
        owner = None
        mark_text = None

        case_data = data.get(
            "case",
            data.get("caseList", [{}])[0] if isinstance(data.get("caseList"), list) else data,
        )
        header = case_data.get("caseHeader", case_data)

        # Mark text
        mark_text = header.get("markLiteralText") or case_data.get("markLiteralText")

        # Status
        status_desc = str(header.get("statusDesc", header.get("statusDescriptionText", "")))
        if status_desc:
            status_text = status_desc

        live_dead = str(
            header.get("liveDeadIndicator", case_data.get("liveDeadIndicator", ""))
        ).upper()
        if (
            "DEAD" in live_dead
            or "CANCELLED" in status_desc.upper()
            or "EXPIRED" in status_desc.upper()
            or "ABANDONED" in status_desc.upper()
        ):
            is_live = False
        elif "LIVE" in live_dead:
            is_live = True

        # Classes & Goods
        class_list = case_data.get("internationalClassList", case_data.get("classes", []))
        if isinstance(class_list, list):
            for c in class_list:
                if isinstance(c, dict) and "classCode" in c:
                    classes.append(str(c["classCode"]).zfill(3))
                elif isinstance(c, str):
                    classes.append(c.strip().zfill(3))

        gs_list = case_data.get("goodsAndServicesList", [])
        if isinstance(gs_list, list) and gs_list:
            goods_services = "; ".join(str(g.get("description", g)) for g in gs_list if g)

        owner_info = (
            case_data.get("ownerList", [{}])[0]
            if isinstance(case_data.get("ownerList"), list)
            else {}
        )
        owner = owner_info.get("partyName") or owner_info.get("name") or case_data.get("ownerName")

        return {
            "serial_number": serial_number,
            "mark_text": mark_text,
            "status": status_text,
            "is_live": is_live,
            "classes": classes,
            "goods_services": goods_services,
            "owner": owner,
            "tsdr_verified": True,
        }
