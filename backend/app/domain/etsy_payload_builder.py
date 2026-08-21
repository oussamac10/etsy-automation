"""Centralized Etsy Open API v3 listing payload builder.

Adheres strictly to Etsy Open API v3 specifications:
- STRICT SAFETY: Hardcodes state="draft". Zero ability to activate or publish automatically.
- Digital listing type="download", is_supply=False.
- Validates and formats price, quantity, tags, shop sections, and renewal preferences.
"""

from __future__ import annotations

from typing import Any
from app.domain.errors import DomainError
from app.domain.pricing import validate_price_minor_units
from app.domain.tags import sanitize_etsy_title, validate_listing_title, validate_tags


def build_etsy_listing_payload(
    title: str,
    description: str,
    tags: list[str],
    price_minor_units: int | None,
    currency: str = "USD",
    taxonomy_id: int | None = None,
    quantity: int = 999,
    shop_section_id: str | int | None = None,
    should_auto_renew: bool = False,
    who_made: str = "i_did",
    when_made: str = "2020_2026",
) -> dict[str, Any]:
    """Assemble a strictly compliant, draft-only Etsy Open API v3 request payload."""
    # 1. Validate & sanitize title to conform to Etsy length and capitalization constraints
    clean_title = sanitize_etsy_title(title)
    title_valid, title_err = validate_listing_title(clean_title)
    if not title_valid:
        raise DomainError(f"Invalid listing title: {title_err}")

    # 2. Validate description
    if not description or not description.strip():
        raise DomainError("Listing description is required.")

    # 3. Normalize tags. The "exactly 13 tags" business rule is enforced earlier in
    # validate_pre_dispatch; here we only reject tags Etsy itself would refuse.
    _, clean_tags, tags_err = validate_tags(tags)
    if not clean_tags:
        raise DomainError(f"Invalid listing tags: {', '.join(tags_err)}")

    # 4. Validate price
    price_valid, price_err = validate_price_minor_units(price_minor_units, currency)
    if not price_valid:
        raise DomainError(f"Invalid listing price: {price_err}")

    assert price_minor_units is not None
    price_decimal = round(price_minor_units / 100.0, 2)

    # 5. Validate taxonomy
    if not taxonomy_id or taxonomy_id <= 0:
        raise DomainError("A valid Etsy seller taxonomy category ID is required.")

    # 6. Validate quantity
    if quantity <= 0:
        quantity = 999

    payload: dict[str, Any] = {
        "title": clean_title[:140],
        "description": description,
        "tags": ",".join(clean_tags[:13]),
        "price": price_decimal,
        "quantity": quantity,
        "taxonomy_id": str(taxonomy_id),
        "who_made": who_made,
        "when_made": when_made,
        "type": "download",  # Digital instant download
        "is_supply": "false",
        "state": "draft",  # STRICT SAFETY RULE: Forced Draft State
        "should_auto_renew": "true" if should_auto_renew else "false",
    }

    if shop_section_id is not None:
        sec_str = str(shop_section_id).strip()
        if sec_str.isdigit() and int(sec_str) > 0:
            payload["shop_section_id"] = int(sec_str)

    return payload

