"""Tests for FakeEtsyProvider and live EtsyProvider HTTP adapter."""

from __future__ import annotations

import httpx
import pytest

from app.ports.errors import ProviderError, ProviderErrorKind
from app.ports.providers import EtsyListingDraftInput
from app.providers.etsy import EtsyProvider
from app.providers.fake import FakeEtsyProvider


class TestFakeEtsyProvider:
    @pytest.mark.asyncio
    async def test_fake_exchange_and_refresh(self) -> None:
        fake = FakeEtsyProvider(default_shop_id="s123", default_shop_name="Studio", default_user_id="u456")

        token_resp = await fake.exchange_code_for_token(code="c1", code_verifier="v1", redirect_uri="http://cb")
        assert token_resp.access_token.startswith("u456")
        assert token_resp.refresh_token.startswith("u456")
        assert "listings_w" in token_resp.scope

        refreshed = await fake.refresh_token(refresh_token=token_resp.refresh_token)
        assert refreshed.access_token != token_resp.access_token

    @pytest.mark.asyncio
    async def test_fake_create_draft_listing_guarantees_draft_state(self) -> None:
        fake = FakeEtsyProvider()
        listing_input = EtsyListingDraftInput(
            title="Vintage Celestial PNG",
            description="High quality PNG sublimation download.",
            tags=["moon", "celestial", "vintage png"],
            price_cents=499,
        )

        resp = await fake.create_draft_listing(
            access_token="token",
            shop_id="s123",
            listing=listing_input,
        )

        # STRICT SAFETY: Output state is always draft
        assert resp.state == "draft"
        assert resp.listing_id is not None
        assert "etsy.com/listing/" in resp.url

    @pytest.mark.asyncio
    async def test_fake_image_and_file_upload(self) -> None:
        fake = FakeEtsyProvider()

        img_resp = await fake.upload_listing_image(
            access_token="token",
            shop_id="s123",
            listing_id="list_1",
            image_bytes=b"mockup-image-bytes",
            filename="mockup.jpg",
            rank=1,
        )
        assert img_resp.listing_image_id is not None
        assert img_resp.rank == 1

        file_resp = await fake.upload_listing_file(
            access_token="token",
            shop_id="s123",
            listing_id="list_1",
            file_bytes=b"zip-file-bytes",
            filename="package.zip",
            rank=1,
        )
        assert file_resp.listing_file_id is not None
        assert file_resp.filesize == len(b"zip-file-bytes")


class TestLiveEtsyProvider:
    @pytest.mark.asyncio
    async def test_auth_error_mapping_401(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid_token", "error_description": "Token expired"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = EtsyProvider(api_key="test_key", client=client)
            with pytest.raises(ProviderError) as exc_info:
                await provider.get_me(access_token="bad_token")

            assert exc_info.value.kind == ProviderErrorKind.AUTHENTICATION
            assert exc_info.value.provider == "etsy"

    @pytest.mark.asyncio
    async def test_rate_limit_mapping_429(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                headers={"retry-after": "5"},
                json={"error": "rate_limit_exceeded"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = EtsyProvider(api_key="test_key", client=client)
            with pytest.raises(ProviderError) as exc_info:
                await provider.get_listing(access_token="t", shop_id="s", listing_id="l")

            assert exc_info.value.kind == ProviderErrorKind.RATE_LIMITED
            assert exc_info.value.retry_after_seconds == 5.0

    @pytest.mark.asyncio
    async def test_create_draft_listing_enforces_draft_payload(self) -> None:
        captured_requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(request)
            return httpx.Response(
                201,
                json={
                    "listing_id": 987654321,
                    "shop_id": 12345,
                    "title": "Vintage Celestial PNG",
                    "state": "draft",
                    "url": "https://www.etsy.com/listing/987654321",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = EtsyProvider(api_key="test_key", client=client)
            listing_input = EtsyListingDraftInput(
                title="Vintage Celestial PNG",
                description="High quality PNG sublimation download.",
                tags=["moon", "celestial"],
                price_cents=599,
            )

            resp = await provider.create_draft_listing(
                access_token="valid_token",
                shop_id="12345",
                listing=listing_input,
            )

            assert resp.listing_id == "987654321"
            assert resp.state == "draft"

            assert len(captured_requests) == 1
            body = captured_requests[0].read().decode()
            # CRITICAL: Verify state=draft is strictly in the form payload sent to Etsy
            assert "state=draft" in body
            assert "type=download" in body
            assert "is_supply=false" in body
