"""Legacy infrastructure facade for mockup product mapping.

Re-exports domain models and helpers from app.domain.mockup_products.
"""

from __future__ import annotations

from app.domain.mockup_products import (
    DEFAULT_SUPPORTED_PRODUCTS,
    PRODUCT_PRESETS,
    MockupProductPreset,
    get_product_preset,
    get_requested_mockup_products,
    normalize_product_type,
)

# Backwards compatibility alias
def normalize_mockup_product(raw: str | None, strict: bool = True) -> str | None:
    return normalize_product_type(raw, strict=strict)

__all__ = [
    "DEFAULT_SUPPORTED_PRODUCTS",
    "PRODUCT_PRESETS",
    "MockupProductPreset",
    "get_product_preset",
    "get_requested_mockup_products",
    "normalize_mockup_product",
    "normalize_product_type",
]
