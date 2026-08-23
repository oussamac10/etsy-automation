"""Application service helper for resolving dynamic customer-facing brand/shop names."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.unit_of_work import UnitOfWork

GENERIC_FALLBACK_SHOP_NAME: str = "Digital Art Studio"


async def resolve_connected_shop_name(
    uow: UnitOfWork,
    owner_id: uuid.UUID | None,
) -> str:
    """Resolve the customer-facing shop name for package branding and legal documents.

    Resolution Priority:
    1. Active connected Etsy shop name from `ShopConnection` (`connection_status == 'connected'`)
    2. Owner-configured shop name from `OwnerSettings.shop_name` (if populated)
    3. Safe generic fallback (`'Digital Art Studio'`) only if neither exists.
    """
    if (
        owner_id is not None
        and hasattr(uow, "shop_connections")
        and uow.shop_connections is not None
    ):
        try:
            conn = await uow.shop_connections.get_by_user_id(owner_id)
            if conn is not None and getattr(conn, "connection_status", None) == "connected":
                raw_name = getattr(conn, "etsy_shop_name", None)
                if isinstance(raw_name, str) and raw_name.strip():
                    return raw_name.strip()
        except Exception:
            pass

    if owner_id is not None and hasattr(uow, "owner_settings") and uow.owner_settings is not None:
        try:
            import inspect

            res = uow.owner_settings.get_for_user(owner_id)
            settings = await res if inspect.isawaitable(res) else res
            if settings is not None:
                raw_shop = getattr(settings, "shop_name", None)
                if isinstance(raw_shop, str) and raw_shop.strip():
                    return raw_shop.strip()
        except Exception:
            pass

    return GENERIC_FALLBACK_SHOP_NAME
