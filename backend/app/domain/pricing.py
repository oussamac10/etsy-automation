"""Pricing calculations, recommendation engine, and validation for Etsy listings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.domain.owner_settings import SUPPORTED_CURRENCIES

DEFAULT_BASE_PRICE_USD_MINOR: Final[int] = 499  # $4.99
MAX_PRICE_MINOR_UNITS: Final[int] = 100_000  # $1,000.00 / €1,000.00 max limit
MIN_PRICE_MINOR_UNITS: Final[int] = 20  # $0.20 minimum listing price on Etsy

# Currency symbols for formatting
CURRENCY_SYMBOLS: Final[dict[str, str]] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "CA$",
    "AUD": "AU$",
}

# Approximate conversion rates for recommended pricing
# (Deterministic baseline recommendations; Etsy converts at merchant shop currency)
CURRENCY_MULTIPLIERS: Final[dict[str, float]] = {
    "USD": 1.0,
    "EUR": 0.95,
    "GBP": 0.80,
    "CAD": 1.35,
    "AUD": 1.50,
}


def resolve_listing_currency(
    listing_currency: str | None = None,
    shop_currency: str | None = None,
    owner_currency: str | None = None,
) -> str:
    """Resolves currency using priority: listing -> shop connection -> owner default -> USD."""
    for candidate in (listing_currency, shop_currency, owner_currency):
        if candidate:
            clean = candidate.upper().strip()
            if clean in SUPPORTED_CURRENCIES:
                return clean
    return "USD"


def resolve_listing_price(
    listing_price_minor: int | None = None,
    owner_default_minor: int | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    currency: str = "USD",
) -> int | None:
    """Resolves the listing price in minor units following strict precedence.

    Priority:
    1. Explicit listing price_minor_units (if set and > 0)
    2. Owner default digital price (if set and > 0)
    3. Deterministic pricing recommendation
    4. None if unavailable (blocks dispatch; NEVER silently defaults to 499).
    """
    if listing_price_minor is not None and listing_price_minor > 0:
        return listing_price_minor

    if owner_default_minor is not None and owner_default_minor > 0:
        return owner_default_minor

    rec = calculate_price_recommendation(
        title=title,
        tags=tags,
        currency=currency,
        owner_default_minor=owner_default_minor,
    )
    if rec and rec.recommended_minor_units > 0:
        return rec.recommended_minor_units

    return None


@dataclass(frozen=True, slots=True)
class PriceRecommendation:
    """Deterministic internal pricing recommendation for a digital listing."""

    recommended_minor_units: int
    currency: str
    formatted_price: str
    rationale: str
    factors: tuple[str, ...] = ()


def format_currency_amount(amount_minor: int, currency: str = "USD") -> str:
    """Format minor units into a human-readable display string."""
    curr_upper = (currency or "USD").upper().strip()
    symbol = CURRENCY_SYMBOLS.get(curr_upper, f"{curr_upper} ")
    amount_decimal = amount_minor / 100.0
    if curr_upper == "EUR":
        return f"€{amount_decimal:.2f}"
    return f"{symbol}{amount_decimal:.2f}"


def validate_price_minor_units(
    price_minor_units: int | None, currency: str = "USD"
) -> tuple[bool, str | None]:
    """Validate price minor units for Etsy listing creation."""
    if price_minor_units is None:
        return False, "Listing price is required."
    if price_minor_units <= 0:
        return False, "Listing price must be greater than zero."
    if price_minor_units < MIN_PRICE_MINOR_UNITS:
        min_fmt = format_currency_amount(MIN_PRICE_MINOR_UNITS, currency)
        return False, f"Listing price cannot be lower than Etsy minimum ({min_fmt})."
    if price_minor_units > MAX_PRICE_MINOR_UNITS:
        max_fmt = format_currency_amount(MAX_PRICE_MINOR_UNITS, currency)
        return False, f"Listing price exceeds safety limit ({max_fmt})."

    curr_upper = (currency or "").upper().strip()
    if curr_upper and curr_upper not in SUPPORTED_CURRENCIES:
        return (
            False,
            f"Unsupported currency '{currency}'. Supported: {', '.join(sorted(SUPPORTED_CURRENCIES))}.",
        )

    return True, None


def calculate_price_recommendation(
    title: str | None = None,
    tags: list[str] | None = None,
    currency: str = "USD",
    owner_default_minor: int | None = None,
) -> PriceRecommendation:
    """Compute a deterministic price recommendation for a commercial digital PNG design package."""
    curr = (currency or "USD").upper().strip()
    if curr not in SUPPORTED_CURRENCIES:
        curr = "USD"

    # Base pricing: Commercial License + 4500x5400 Master PNG + Print-Ready PDF + Sizing Guide
    base_cents = (
        owner_default_minor
        if (owner_default_minor and owner_default_minor > 0)
        else DEFAULT_BASE_PRICE_USD_MINOR
    )

    factors: list[str] = [
        "Standard 4500x5400 300 DPI Transparent Master PNG",
        "Print-Ready PDF & Commercial License included",
    ]

    text_corpus = f"{title or ''} {' '.join(tags or [])}".lower()

    # Premium factor: Bundle / Multi-element design
    is_bundle = any(kw in text_corpus for kw in ("bundle", "pack", "collection", "set", "elements"))
    # Seasonal / High Demand factor (e.g. Christmas, Halloween, Mother's Day)
    is_seasonal_rush = any(
        kw in text_corpus for kw in ("christmas", "xmas", "halloween", "easter", "valentine")
    )

    addon_cents = 0
    if is_bundle:
        addon_cents += 200
        factors.append("Multi-design bundle / collection detected (+2.00)")
    elif is_seasonal_rush:
        addon_cents += 50
        factors.append("High seasonal holiday demand (+0.50)")

    total_usd = base_cents + addon_cents

    # Adjust for target currency
    multiplier = CURRENCY_MULTIPLIERS.get(curr, 1.0)
    converted = round(total_usd * multiplier)

    # Standard charm pricing rounding (e.g. end in .99 or .50)
    # If converted ends close to 99, snap to 99
    rem = converted % 100
    if rem != 99:
        if rem >= 75:
            recommended_minor = (converted // 100) * 100 + 99
        elif rem >= 25:
            recommended_minor = (converted // 100) * 100 + 49
        else:
            recommended_minor = max(MIN_PRICE_MINOR_UNITS, (converted // 100) * 100 - 1)
            if recommended_minor <= 0:
                recommended_minor = 99
    else:
        recommended_minor = converted

    formatted = format_currency_amount(recommended_minor, curr)
    rationale = f"Recommended based on digital sublimation asset specs, included print PDF, and commercial rights in {curr}."

    return PriceRecommendation(
        recommended_minor_units=recommended_minor,
        currency=curr,
        formatted_price=formatted,
        rationale=rationale,
        factors=tuple(factors),
    )
