"""Money.

Never a float. Amounts are held as integer **minor units** (US cents for USD),
because that is the only representation that survives storage, addition and
comparison without rounding surprises. ``Decimal`` is used at the boundaries
where a human reads or writes an amount.

The cost ledger stores minor units in a ``BIGINT`` column plus a currency code.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final, Self

#: Exponent per supported currency. Extend deliberately: a currency with a
#: different exponent (JPY has 0) breaks any assumption of "always 2".
CURRENCY_EXPONENT: Final[dict[str, int]] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
}

DEFAULT_CURRENCY: Final[str] = "USD"


class MoneyError(ValueError):
    """Base class for money errors."""


class UnsupportedCurrencyError(MoneyError):
    def __init__(self, currency: str) -> None:
        super().__init__(
            f"Unsupported currency {currency!r}; add it to CURRENCY_EXPONENT "
            "with its correct exponent before using it."
        )
        self.currency = currency


class CurrencyMismatchError(MoneyError):
    def __init__(self, left: str, right: str) -> None:
        super().__init__(f"Cannot combine {left} and {right}.")
        self.left = left
        self.right = right


@dataclass(frozen=True, slots=True, order=False)
class Money:
    """An exact amount in one currency, held as integer minor units."""

    minor_units: int
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self) -> None:
        if not isinstance(self.minor_units, int) or isinstance(self.minor_units, bool):
            raise MoneyError("minor_units must be an int")
        if self.currency not in CURRENCY_EXPONENT:
            raise UnsupportedCurrencyError(self.currency)

    # -- construction -------------------------------------------------------

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> Self:
        return cls(0, currency)

    @classmethod
    def from_decimal(cls, amount: Decimal | str | int, currency: str = DEFAULT_CURRENCY) -> Self:
        """Build from a major-unit amount such as ``Decimal("0.041")``.

        Sub-minor-unit precision is rounded half-up, because a provider price of
        $0.0041 per call still has to be stored as an integer number of cents.
        Callers that need to keep fractional precision should accumulate units
        first and convert once.
        """
        if currency not in CURRENCY_EXPONENT:
            raise UnsupportedCurrencyError(currency)
        try:
            value = Decimal(amount) if not isinstance(amount, Decimal) else amount
        except (InvalidOperation, TypeError) as exc:
            raise MoneyError(f"Not a valid decimal amount: {amount!r}") from exc
        if not value.is_finite():
            raise MoneyError(f"Amount must be finite, got {value}")

        scale = Decimal(10) ** CURRENCY_EXPONENT[currency]
        scaled = (value * scale).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return cls(int(scaled), currency)

    # -- reading ------------------------------------------------------------

    @property
    def exponent(self) -> int:
        return CURRENCY_EXPONENT[self.currency]

    def to_decimal(self) -> Decimal:
        """The major-unit amount, exact."""
        return (Decimal(self.minor_units) / (Decimal(10) ** self.exponent)).quantize(
            Decimal(1).scaleb(-self.exponent)
        )

    def __str__(self) -> str:
        return f"{self.to_decimal()} {self.currency}"

    # -- arithmetic ---------------------------------------------------------

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency)

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.minor_units + other.minor_units, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.minor_units - other.minor_units, self.currency)

    def __mul__(self, factor: int) -> Money:
        if not isinstance(factor, int) or isinstance(factor, bool):
            raise MoneyError("Money may only be multiplied by an int")
        return Money(self.minor_units * factor, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.minor_units < other.minor_units

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.minor_units <= other.minor_units

    def __gt__(self, other: Money) -> bool:
        self._check(other)
        return self.minor_units > other.minor_units

    def __ge__(self, other: Money) -> bool:
        self._check(other)
        return self.minor_units >= other.minor_units

    @property
    def is_zero(self) -> bool:
        return self.minor_units == 0


def total(amounts: list[Money], currency: str = DEFAULT_CURRENCY) -> Money:
    """Sum a list of amounts.

    An empty list returns zero in ``currency`` rather than raising, so a
    workflow with no spend reports ``0.00`` instead of nothing.
    """
    result = Money.zero(currency)
    for amount in amounts:
        result = result + amount
    return result
