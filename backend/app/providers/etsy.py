"""Official Etsy Open API v3 HTTP adapter.

Adheres strictly to Etsy Open API v3 specifications:
- OAuth 2.0 Authorization Code Flow with PKCE
- Listing Draft Creation (draft-only enforcement)
- Listing Mockup Image Uploads (multipart/form-data)
- Digital Listing Files Upload (multipart/form-data)
- Rate limiting and exponential backoff handling
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import Any
import httpx
import structlog

from app.ports.errors import ProviderError, ProviderErrorKind
from app.domain.etsy_payload_builder import build_etsy_listing_payload
from app.ports.providers import (
    EtsyFileResponse,
    EtsyGateway,
    EtsyImageResponse,
    EtsyListingDraftInput,
    EtsyListingResponse,
    EtsyShop,
    EtsyShopSection,
    EtsyTaxonomyNode,
    EtsyTaxonomyProperty,
    EtsyTokenResponse,
    EtsyUser,
)

logger = structlog.get_logger(__name__)

DEFAULT_ETSY_API_BASE = "https://openapi.etsy.com/v3"
DEFAULT_ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TRANSIENT_RETRIES = 3


class EtsyProvider(EtsyGateway):
    """Live Etsy Open API v3 Gateway."""

    def __init__(
        self,
        api_key: str,
        shared_secret: str | None = None,
        base_url: str = DEFAULT_ETSY_API_BASE,
        token_url: str = DEFAULT_ETSY_TOKEN_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._shared_secret = shared_secret
        self._base_url = base_url.rstrip("/")
        self._token_url = token_url
        self._timeout = timeout
        self._client = client
        self._taxonomy_cache: list[EtsyTaxonomyNode] | None = None
        self._taxonomy_cache_time: float = 0.0
        self._taxonomy_properties_cache: dict[int, list[EtsyTaxonomyProperty]] = {}

    def _default_headers(self, access_token: str | None = None) -> dict[str, str]:
        api_header_value = (
            f"{self._api_key}:{self._shared_secret}"
            if self._shared_secret
            else self._api_key
        )
        headers = {
            "x-api-key": api_header_value,
            "Accept": "application/json",
            "User-Agent": "EtsyPngAutomation/1.0",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _handle_response_errors(self, response: httpx.Response, operation: str) -> None:
        if response.status_code in (401, 403):
            logger.error("etsy_auth_error", status_code=response.status_code, operation=operation)
            raise ProviderError(
                kind=ProviderErrorKind.AUTHENTICATION,
                provider="etsy",
                operation=operation,
                message=f"Etsy authentication failed (status {response.status_code}): {response.text}",
            )

        if response.status_code in (404, 410):
            logger.info("etsy_not_found", status_code=response.status_code, operation=operation)
            raise ProviderError(
                kind=ProviderErrorKind.NOT_FOUND,
                provider="etsy",
                operation=operation,
                message=f"Etsy resource not found (status {response.status_code}): {response.text}",
            )

        if response.status_code == 429:
            retry_after_str = response.headers.get("retry-after")
            retry_after: float = 2.0
            if retry_after_str:
                try:
                    retry_after = float(retry_after_str)
                except ValueError:
                    retry_after = 2.0
            logger.warning("etsy_rate_limit_exceeded", operation=operation, retry_after=retry_after)
            raise ProviderError(
                kind=ProviderErrorKind.RATE_LIMITED,
                provider="etsy",
                operation=operation,
                message="Etsy API rate limit reached (HTTP 429).",
                retry_after_seconds=retry_after,
            )

        if response.status_code == 400 or response.status_code == 422:
            logger.warning("etsy_invalid_request", status_code=response.status_code, operation=operation, detail=response.text)
            raise ProviderError(
                kind=ProviderErrorKind.INVALID_REQUEST,
                provider="etsy",
                operation=operation,
                message=f"Etsy request validation error ({response.status_code}): {response.text}",
            )

        if response.status_code >= 500:
            logger.error("etsy_server_error", status_code=response.status_code, operation=operation)
            raise ProviderError(
                kind=ProviderErrorKind.RETRYABLE,
                provider="etsy",
                operation=operation,
                message=f"Etsy remote server error (status {response.status_code}).",
            )

        if not (200 <= response.status_code < 300):
            logger.error("etsy_unexpected_status", status_code=response.status_code, operation=operation)
            raise ProviderError(
                kind=ProviderErrorKind.PERMANENT,
                provider="etsy",
                operation=operation,
                message=f"Unexpected status code {response.status_code} from Etsy: {response.text}",
            )

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: Any | None = None,
        operation: str,
    ) -> httpx.Response:
        """Executes an HTTP request with bounded exponential backoff for transient 429/5xx errors."""
        attempts = 0
        while True:
            attempts += 1
            try:
                if self._client is not None:
                    response = await self._client.request(
                        method,
                        url,
                        headers=headers,
                        data=data,
                        json=json_body,
                        files=files,
                        timeout=self._timeout,
                    )
                else:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.request(
                            method,
                            url,
                            headers=headers,
                            data=data,
                            json=json_body,
                            files=files,
                        )

                if response.status_code in (429, 502, 503, 504) and attempts < MAX_TRANSIENT_RETRIES:
                    retry_wait = float(response.headers.get("retry-after", 0.5 * (2 ** (attempts - 1))))
                    jitter = random.uniform(0.1, 0.4)
                    await asyncio.sleep(retry_wait + jitter)
                    continue

                self._handle_response_errors(response, operation)
                return response

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempts < MAX_TRANSIENT_RETRIES:
                    await asyncio.sleep(0.5 * (2 ** (attempts - 1)) + random.uniform(0.1, 0.3))
                    continue
                raise ProviderError(
                    kind=ProviderErrorKind.RETRYABLE,
                    provider="etsy",
                    operation=operation,
                    message=f"Network communication failed with Etsy: {exc}",
                ) from exc

    async def exchange_code_for_token(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> EtsyTokenResponse:
        """Exchange OAuth 2.0 PKCE authorization code for access and refresh tokens."""
        url = self._token_url
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "EtsyPngAutomation/1.0",
        }
        data = {
            "grant_type": "authorization_code",
            "client_id": self._api_key,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        }
        response = await self._execute_with_retry("POST", url, headers=headers, data=data, operation="exchange_code")
        payload = response.json()

        scopes: list[str] = []
        raw_scope = payload.get("scope", "")
        if isinstance(raw_scope, str):
            scopes = [s.strip() for s in raw_scope.split() if s.strip()]
        elif isinstance(raw_scope, list):
            scopes = [str(s).strip() for s in raw_scope if str(s).strip()]

        return EtsyTokenResponse(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload.get("refresh_token", "")),
            expires_in=int(payload.get("expires_in", 3600)),
            token_type=str(payload.get("token_type", "Bearer")),
            scope=scopes,
        )

    async def refresh_token(self, *, refresh_token: str) -> EtsyTokenResponse:
        """Refresh expired access token using refresh_token grant."""
        url = self._token_url
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "EtsyPngAutomation/1.0",
        }
        data = {
            "grant_type": "refresh_token",
            "client_id": self._api_key,
            "refresh_token": refresh_token,
        }
        response = await self._execute_with_retry("POST", url, headers=headers, data=data, operation="refresh_token")
        payload = response.json()

        scopes: list[str] = []
        raw_scope = payload.get("scope", "")
        if isinstance(raw_scope, str):
            scopes = [s.strip() for s in raw_scope.split() if s.strip()]
        elif isinstance(raw_scope, list):
            scopes = [str(s).strip() for s in raw_scope if str(s).strip()]

        return EtsyTokenResponse(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload.get("refresh_token", refresh_token)),
            expires_in=int(payload.get("expires_in", 3600)),
            token_type=str(payload.get("token_type", "Bearer")),
            scope=scopes,
        )

    async def get_me(self, *, access_token: str) -> EtsyUser:
        """Fetch current user identity."""
        url = f"{self._base_url}/application/users/me"
        headers = self._default_headers(access_token)
        response = await self._execute_with_retry("GET", url, headers=headers, operation="get_me")
        payload = response.json()
        return EtsyUser(
            user_id=str(payload.get("user_id", "")),
            primary_email=payload.get("primary_email"),
            first_name=payload.get("first_name"),
        )

    async def get_user_shops(self, *, access_token: str, user_id: str) -> list[EtsyShop]:
        """Fetch user's Etsy shops."""
        url = f"{self._base_url}/application/users/{user_id}/shops"
        headers = self._default_headers(access_token)
        response = await self._execute_with_retry("GET", url, headers=headers, operation="get_user_shops")
        payload = response.json()
        results = payload.get("results", [])
        if not results and "shop_id" in payload:
            results = [payload]

        shops: list[EtsyShop] = []
        for item in results:
            shops.append(
                EtsyShop(
                    shop_id=str(item["shop_id"]),
                    shop_name=str(item["shop_name"]),
                    user_id=str(item.get("user_id", user_id)),
                    url=item.get("url"),
                    icon_url=item.get("icon_url_fullxfull"),
                )
            )
        return shops

    async def create_draft_listing(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing: EtsyListingDraftInput,
        idempotency_key: str | None = None,
    ) -> EtsyListingResponse:
        """Create draft digital listing on Etsy Open API v3.

        CRITICAL: The state is hardcoded to 'draft'. Under no circumstances can active/published be requested.
        """
        url = f"{self._base_url}/application/shops/{shop_id}/listings"
        headers = self._default_headers(access_token)
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        data: dict[str, Any] = build_etsy_listing_payload(
            title=listing.title,
            description=listing.description,
            tags=listing.tags,
            price_minor_units=listing.price_cents,
            currency=listing.currency,
            taxonomy_id=listing.taxonomy_id,
            quantity=listing.quantity,
            shop_section_id=listing.shop_section_id,
            should_auto_renew=listing.should_auto_renew,
            who_made=listing.who_made,
            when_made=listing.when_made,
        )

        response = await self._execute_with_retry("POST", url, headers=headers, data=data, operation="create_draft_listing")
        payload = response.json()

        listing_id = str(payload.get("listing_id", ""))
        return EtsyListingResponse(
            listing_id=listing_id,
            shop_id=str(payload.get("shop_id", shop_id)),
            title=str(payload.get("title", listing.title)),
            state="draft",
            url=payload.get("url") or f"https://www.etsy.com/listing/{listing_id}",
        )

    async def upload_listing_image(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing_id: str,
        image_bytes: bytes,
        filename: str = "mockup.jpg",
        rank: int = 1,
        alt_text: str | None = None,
    ) -> EtsyImageResponse:
        """Upload preview/mockup image for an Etsy listing draft."""
        url = f"{self._base_url}/application/shops/{shop_id}/listings/{listing_id}/images"
        headers = self._default_headers(access_token)

        content_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        files = {
            "image": (filename, image_bytes, content_type),
        }
        data: dict[str, str] = {
            "rank": str(rank),
        }
        if alt_text:
            data["alt_text"] = alt_text[:250]

        response = await self._execute_with_retry(
            "POST", url, headers=headers, data=data, files=files, operation="upload_listing_image"
        )
        payload = response.json()
        return EtsyImageResponse(
            listing_image_id=str(payload.get("listing_image_id", "")),
            listing_id=str(payload.get("listing_id", listing_id)),
            rank=int(payload.get("rank", rank)),
            url=payload.get("url_fullxfull"),
        )

    async def upload_listing_file(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing_id: str,
        file_bytes: bytes,
        filename: str = "package.zip",
        rank: int = 1,
    ) -> EtsyFileResponse:
        """Upload customer digital download ZIP file for a digital listing draft."""
        url = f"{self._base_url}/application/shops/{shop_id}/listings/{listing_id}/files"
        headers = self._default_headers(access_token)

        # Sanitize and strictly enforce Etsy filename constraints (3 to 70 characters)
        clean_fn = re.sub(r"[^a-zA-Z0-9_.-]+", "_", filename)
        clean_fn = re.sub(r"_+", "_", clean_fn).strip("_-")
        if len(clean_fn) > 68:
            if "." in clean_fn:
                stem, ext = clean_fn.rsplit(".", 1)
                ext = f".{ext}"
            else:
                stem, ext = clean_fn, ""
            clean_fn = f"{stem[: 68 - len(ext)].rstrip('_-.')}{ext}"
        if len(clean_fn) < 3:
            clean_fn = f"file_{clean_fn}" if clean_fn else "file.zip"

        mime_type = "application/zip"
        lower_fn = clean_fn.lower()
        if lower_fn.endswith(".png"):
            mime_type = "image/png"
        elif lower_fn.endswith(".pdf"):
            mime_type = "application/pdf"
        elif lower_fn.endswith(".jpg") or lower_fn.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif lower_fn.endswith(".txt"):
            mime_type = "text/plain"

        files = {
            "file": (clean_fn, file_bytes, mime_type),
        }
        data = {
            "name": clean_fn,
            "rank": str(rank),
        }

        response = await self._execute_with_retry(
            "POST", url, headers=headers, data=data, files=files, operation="upload_listing_file"
        )
        payload = response.json()
        return EtsyFileResponse(
            listing_file_id=str(payload.get("listing_file_id", "")),
            listing_id=str(payload.get("listing_id", listing_id)),
            rank=int(payload.get("rank", rank)),
            filename=str(payload.get("filename", filename)),
            filesize=payload.get("filesize"),
        )

    async def get_listing(
        self, *, access_token: str, shop_id: str, listing_id: str
    ) -> EtsyListingResponse | None:
        """Retrieve existing Etsy listing metadata, returning None if listing is not found / deleted."""
        url = f"{self._base_url}/application/listings/{listing_id}"
        headers = self._default_headers(access_token)
        try:
            response = await self._execute_with_retry("GET", url, headers=headers, operation="get_listing")
            payload = response.json()
            state = str(payload.get("state", "draft")).lower()
            if state in ("deleted", "removed"):
                return None
            return EtsyListingResponse(
                listing_id=str(payload.get("listing_id", listing_id)),
                shop_id=str(payload.get("shop_id", shop_id)),
                title=str(payload.get("title", "")),
                state=state,
                url=payload.get("url") or f"https://www.etsy.com/listing/{listing_id}",
            )
        except ProviderError as pe:
            if pe.kind == ProviderErrorKind.NOT_FOUND:
                return None
            raise

    async def get_seller_taxonomy_nodes(self) -> list[EtsyTaxonomyNode]:
        """Fetch all official Etsy seller taxonomy nodes with 24h caching."""
        import time

        now = time.time()
        if self._taxonomy_cache is not None and (now - self._taxonomy_cache_time) < 86400:
            return self._taxonomy_cache

        url = f"{self._base_url}/application/seller-taxonomy/nodes"
        headers = self._default_headers()
        response = await self._execute_with_retry(
            "GET", url, headers=headers, operation="get_seller_taxonomy_nodes"
        )
        payload = response.json()
        raw_results = payload.get("results", [])

        def parse_node(raw: dict[str, Any], parent_path: str = "") -> EtsyTaxonomyNode:
            name = str(raw.get("name", ""))
            current_path = f"{parent_path} > {name}" if parent_path else name
            raw_children = raw.get("children") or []
            parsed_children = tuple(parse_node(c, current_path) for c in raw_children)
            return EtsyTaxonomyNode(
                id=int(raw.get("id", 0)),
                level=int(raw.get("level", 0)),
                name=name,
                parent_id=raw.get("parent_id"),
                children=parsed_children,
                full_path=current_path,
            )

        parsed_nodes = [parse_node(r, "") for r in raw_results]
        self._taxonomy_cache = parsed_nodes
        self._taxonomy_cache_time = now
        return parsed_nodes

    async def get_shop_sections(self, *, access_token: str, shop_id: str) -> list[EtsyShopSection]:
        """Fetch all active shop sections for an Etsy shop."""
        url = f"{self._base_url}/application/shops/{shop_id}/sections"
        headers = self._default_headers(access_token)
        try:
            response = await self._execute_with_retry("GET", url, headers=headers, operation="get_shop_sections")
            payload = response.json()
            results = payload.get("results", [])
            sections: list[EtsyShopSection] = []
            for item in results:
                sections.append(
                    EtsyShopSection(
                        shop_section_id=str(item.get("shop_section_id", "")),
                        title=str(item.get("title", "")),
                        rank=int(item.get("rank", 0)),
                        active_listing_count=int(item.get("active_listing_count", 0)),
                    )
                )
            return sections
        except Exception as exc:
            logger.warning("etsy_get_shop_sections_failed", shop_id=shop_id, error=str(exc))
            return []

    async def create_shop_section(self, *, access_token: str, shop_id: str, title: str) -> EtsyShopSection:
        """Create a new shop section on Etsy."""
        url = f"{self._base_url}/application/shops/{shop_id}/sections"
        headers = self._default_headers(access_token)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = {"title": title.strip()}

        response = await self._execute_with_retry("POST", url, headers=headers, data=data, operation="create_shop_section")
        payload = response.json()
        return EtsyShopSection(
            shop_section_id=str(payload.get("shop_section_id", "")),
            title=str(payload.get("title", title)),
            rank=int(payload.get("rank", 0)),
            active_listing_count=0,
        )

    async def get_taxonomy_properties(self, *, taxonomy_id: int) -> list[EtsyTaxonomyProperty]:
        """Fetch official Etsy taxonomy properties/attributes for a category node."""
        if taxonomy_id in self._taxonomy_properties_cache:
            return self._taxonomy_properties_cache[taxonomy_id]

        url = f"{self._base_url}/application/seller-taxonomy/nodes/{taxonomy_id}/properties"
        headers = self._default_headers()
        try:
            response = await self._execute_with_retry("GET", url, headers=headers, operation="get_taxonomy_properties")
            payload = response.json()
            results = payload.get("results", [])
            properties: list[EtsyTaxonomyProperty] = []
            for item in results:
                raw_values = item.get("possible_values", [])
                parsed_values = [
                    {"value_id": int(v.get("value_id", 0)), "name": str(v.get("name", ""))}
                    for v in raw_values
                    if v.get("value_id") is not None
                ]
                properties.append(
                    EtsyTaxonomyProperty(
                        property_id=int(item.get("property_id", 0)),
                        name=str(item.get("name", "")),
                        is_required=bool(item.get("is_required", False)),
                        supports_attributes=bool(item.get("supports_attributes", False)),
                        is_multivalued=bool(item.get("is_multivalued", False)),
                        possible_values=parsed_values,
                    )
                )
            self._taxonomy_properties_cache[taxonomy_id] = properties
            return properties
        except Exception as exc:
            logger.warning("etsy_get_taxonomy_properties_failed", taxonomy_id=taxonomy_id, error=str(exc))
            return []

    async def update_listing_property(
        self,
        *,
        access_token: str,
        shop_id: str,
        listing_id: str,
        property_id: int,
        value_ids: list[int] | None = None,
        values: list[str] | None = None,
    ) -> bool:
        """Update a specific listing property attribute on Etsy."""
        url = f"{self._base_url}/application/shops/{shop_id}/listings/{listing_id}/properties/{property_id}"
        headers = self._default_headers(access_token)
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        data: dict[str, Any] = {}
        if value_ids:
            data["value_ids"] = ",".join(str(vid) for vid in value_ids)
        if values:
            data["values"] = ",".join(values)

        try:
            await self._execute_with_retry("PUT", url, headers=headers, data=data, operation="update_listing_property")
            return True
        except Exception as exc:
            logger.warning("etsy_update_listing_property_failed", listing_id=listing_id, property_id=property_id, error=str(exc))
            return False

    async def update_listing_inventory(
        self,
        *,
        access_token: str,
        listing_id: str,
        sku: str,
        price_cents: int,
        quantity: int,
    ) -> bool:
        """Update listing inventory SKU, price, and quantity."""
        url = f"{self._base_url}/application/listings/{listing_id}/inventory"
        headers = self._default_headers(access_token)
        headers["Content-Type"] = "application/json"

        price_decimal = round(price_cents / 100.0, 2)
        json_body = {
            "products": [
                {
                    "sku": sku,
                    "offerings": [
                        {
                            "price": price_decimal,
                            "quantity": quantity,
                            "is_enabled": True,
                        }
                    ],
                }
            ]
        }

        try:
            await self._execute_with_retry("PUT", url, headers=headers, json_body=json_body, operation="update_listing_inventory")
            return True
        except Exception as exc:
            logger.warning("etsy_update_listing_inventory_failed", listing_id=listing_id, sku=sku, error=str(exc))
            return False
