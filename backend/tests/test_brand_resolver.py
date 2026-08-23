"""Tests for dynamic connected Etsy shop name resolution and branding."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.brand_resolver import (
    GENERIC_FALLBACK_SHOP_NAME,
    resolve_connected_shop_name,
)
from app.domain.package_builder import (
    generate_instructions_text,
    generate_license_text,
    sanitize_brand_slug,
    sanitize_display_title,
    sanitize_product_title,
)
from app.infrastructure.models.shop_connection import ShopConnection


@pytest.mark.asyncio
async def test_resolve_connected_shop_name_priority_etsy_connection():
    """ShopConnection with connected status takes highest priority."""
    owner_id = uuid.uuid4()
    mock_conn = MagicMock(spec=ShopConnection)
    mock_conn.connection_status = "connected"
    mock_conn.etsy_shop_name = "NovaCraftPixel"

    uow = MagicMock()
    uow.shop_connections.get_by_user_id = AsyncMock(return_value=mock_conn)

    resolved = await resolve_connected_shop_name(uow, owner_id)
    assert resolved == "NovaCraftPixel"


@pytest.mark.asyncio
async def test_resolve_connected_shop_name_switches_on_reconnect():
    """Reconnecting to a different Etsy shop updates resolved name immediately."""
    owner_id = uuid.uuid4()

    # Shop A
    mock_conn_a = MagicMock(spec=ShopConnection)
    mock_conn_a.connection_status = "connected"
    mock_conn_a.etsy_shop_name = "NovaCraftPixel"

    uow = MagicMock()
    uow.shop_connections.get_by_user_id = AsyncMock(return_value=mock_conn_a)

    resolved_a = await resolve_connected_shop_name(uow, owner_id)
    assert resolved_a == "NovaCraftPixel"

    # Shop B
    mock_conn_b = MagicMock(spec=ShopConnection)
    mock_conn_b.connection_status = "connected"
    mock_conn_b.etsy_shop_name = "PixelMoonStudio"
    uow.shop_connections.get_by_user_id = AsyncMock(return_value=mock_conn_b)

    resolved_b = await resolve_connected_shop_name(uow, owner_id)
    assert resolved_b == "PixelMoonStudio"


@pytest.mark.asyncio
async def test_resolve_connected_shop_name_disconnected_fallback_to_owner_settings():
    """Disconnected Etsy connection falls back to owner_settings.shop_name if available."""
    owner_id = uuid.uuid4()
    mock_conn = MagicMock(spec=ShopConnection)
    mock_conn.connection_status = "disconnected"
    mock_conn.etsy_shop_name = "OldShop"

    mock_settings = MagicMock()
    mock_settings.shop_name = "CustomStudioBrand"

    uow = MagicMock()
    uow.shop_connections.get_by_user_id = AsyncMock(return_value=mock_conn)
    uow.owner_settings.get_for_user = AsyncMock(return_value=mock_settings)

    resolved = await resolve_connected_shop_name(uow, owner_id)
    assert resolved == "CustomStudioBrand"


@pytest.mark.asyncio
async def test_resolve_connected_shop_name_safe_generic_fallback():
    """Missing connection and settings resolves to generic safe fallback."""
    owner_id = uuid.uuid4()
    uow = MagicMock()
    uow.shop_connections.get_by_user_id = AsyncMock(return_value=None)
    uow.owner_settings.get_for_user = AsyncMock(return_value=None)

    resolved = await resolve_connected_shop_name(uow, owner_id)
    assert resolved == GENERIC_FALLBACK_SHOP_NAME


def test_sanitize_brand_slug():
    """Brand slugs are deterministic and filesystem safe."""
    assert sanitize_brand_slug("NovaCraftPixel") == "NovaCraftPixel"
    assert sanitize_brand_slug("Pixel Moon & Studio!") == "Pixel_Moon_Studio"
    assert sanitize_brand_slug("  --Cool***Designs--  ") == "Cool_Designs"
    assert sanitize_brand_slug("") == "Shop"


def test_sanitize_product_title():
    """Product titles are concise and free of punctuation."""
    assert (
        sanitize_product_title(
            "Cozy Fall Book Lover PNG Digital Download, Bookish Autumn Sublimation Design"
        )
        == "Cozy_Fall_Book_Lover_PNG_Digital_Downloa"
    )
    assert sanitize_product_title("Vintage Mushroom - DTG Clipart | Cute Art") == "Vintage_Mushroom"
    assert sanitize_product_title("") == "Artwork"


def test_sanitize_display_title():
    """Display titles in legal documents stay clean without long SEO chains."""
    assert (
        sanitize_display_title("Cozy Fall Book Lover, Autumn Sublimation PNG Design")
        == "Cozy Fall Book Lover"
    )


def test_license_text_branding():
    """LICENSE.txt dynamically embeds shop name."""
    lic_a = generate_license_text("NovaCraftPixel", "Cozy Fall Book Lover")
    assert "Issued By: NovaCraftPixel" in lic_a
    assert "Support: Contact NovaCraftPixel through Etsy Messages." in lic_a
    assert "Product: Cozy Fall Book Lover" in lic_a

    lic_b = generate_license_text("PixelMoonStudio", "Cozy Fall Book Lover")
    assert "Issued By: PixelMoonStudio" in lic_b
    assert "Support: Contact PixelMoonStudio through Etsy Messages." in lic_b


def test_instructions_text_branding():
    """INSTRUCTIONS.txt dynamically embeds shop name and concise title."""
    inst_a = generate_instructions_text("Cozy Fall Book Lover", shop_name="NovaCraftPixel")
    assert "Need assistance? Contact NovaCraftPixel via Etsy Messages." in inst_a
    assert "Artwork: Cozy Fall Book Lover" in inst_a

    inst_b = generate_instructions_text("Cozy Fall Book Lover", shop_name="PixelMoonStudio")
    assert "Need assistance? Contact PixelMoonStudio via Etsy Messages." in inst_b
