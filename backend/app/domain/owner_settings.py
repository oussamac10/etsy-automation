"""The owner's persistent preferences.

Framework-free: the supported vocabulary and the numeric bounds live here so the
API schema, the database constraints and the tests all read the same list rather
than three drifting copies.

Nothing here promises a market outcome. A marketplace and a currency are
configuration, not a claim that a market is good.
"""

from __future__ import annotations

from decimal import Decimal

#: Marketplaces the product can prepare a draft for. Only Etsy exists in the
#: MVP; the set is here so adding one is a deliberate change with a migration.
SUPPORTED_MARKETPLACES: frozenset[str] = frozenset({"etsy"})

#: The Etsy shop currencies this tool understands. Budgets are denominated in
#: the settings currency, so an unsupported code would make the ledger
#: meaningless rather than merely wrong.
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR", "GBP", "CAD", "AUD"})

#: ISO 3166-1 alpha-2, validated by shape rather than by an embedded country
#: list that would need maintaining. The API enforces the two-letter pattern.
DEFAULT_TARGET_COUNTRY = "US"
DEFAULT_MARKETPLACE = "etsy"
DEFAULT_CURRENCY = "USD"
DEFAULT_LANGUAGE = "en"

#: Budget ceilings. Zero means "no paid work at all", which is a legitimate
#: setting and the reason the lower bound is 0 rather than a positive minimum.
MIN_BUDGET = Decimal("0.00")
MAX_DAILY_BUDGET = Decimal("1000.00")
MAX_MONTHLY_BUDGET = Decimal("10000.00")
DEFAULT_DAILY_BUDGET = Decimal("2.00")
DEFAULT_MONTHLY_BUDGET = Decimal("30.00")

#: Free-text preference limits, enforced at the API and by CHECK constraints.
MAX_STYLE_PREFERENCES = 20
MAX_STYLE_PREFERENCE_LENGTH = 120
MAX_AVOID_TERMS = 50
MAX_PRODUCT_USES = 20
MAX_NOTES_LENGTH = 2000

#: Default Etsy listing settings.
DEFAULT_DIGITAL_PRICE_MINOR = 499
DEFAULT_DIGITAL_QUANTITY = 999
DEFAULT_AUTO_RENEW = False
DEFAULT_SHOP_SECTION_STRATEGY = "auto"


class BudgetRelationError(ValueError):
    """A daily ceiling above the monthly ceiling is always a mistake."""

    def __init__(self, daily: Decimal, monthly: Decimal) -> None:
        super().__init__(
            f"daily budget {daily} cannot exceed the monthly budget {monthly}; "
            "the daily limit would never bind."
        )
        self.daily = daily
        self.monthly = monthly


def validate_budgets(daily: Decimal, monthly: Decimal) -> None:
    """Cross-field rule the database also enforces as a CHECK constraint."""
    if daily > monthly:
        raise BudgetRelationError(daily, monthly)
