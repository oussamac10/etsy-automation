"""Media and mockup ordering with primary hero image selection for Etsy listings."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.models.artwork import Asset


def order_listing_mockup_assets(
    mockups: list[Asset],
    master_asset: Asset,
    primary_mockup_asset_id: uuid.UUID | None = None,
    max_images: int = 10,
) -> list[Asset]:
    """Order mockup preview assets for Etsy upload (Rank 1 to 10).

    1. If `primary_mockup_asset_id` matches an active mockup, it becomes Rank 1.
    2. Remaining active mockups follow in stable order.
    3. If no active mockups exist, falls back to `master_asset`.
    4. Capped at `max_images` (Etsy limit is 10).
    """
    if not mockups:
        return [master_asset]

    ordered: list[Asset] = []

    # If primary mockup specified and present, place it first
    if primary_mockup_asset_id is not None:
        primary_match = next((m for m in mockups if m.id == primary_mockup_asset_id), None)
        if primary_match is not None:
            ordered.append(primary_match)

    # If no explicit primary match, prioritize the mockup marked as cover
    if not ordered:
        cover_match = next(
            (m for m in mockups if m.provenance and m.provenance.get("is_cover") is True),
            None,
        )
        if cover_match is not None:
            ordered.append(cover_match)

    for m in mockups:
        if m not in ordered:
            ordered.append(m)

    return ordered[:max_images]
