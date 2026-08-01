"""Money precision.

The cost ledger is the reason this type exists: an amount that drifts by a
fraction of a cent per operation would make the budget check quietly wrong.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.money import (
    CurrencyMismatchError,
    Money,
    MoneyError,
    UnsupportedCurrencyError,
    total,
)


class TestConstruction:
    def test_zero(self) -> None:
        assert Money.zero().minor_units == 0
        assert Money.zero().currency == "USD"

    def test_from_decimal_converts_to_minor_units(self) -> None:
        assert Money.from_decimal(Decimal("1.00")).minor_units == 100
        assert Money.from_decimal(Decimal("0.041")).minor_units == 4
        assert Money.from_decimal("12.34").minor_units == 1234

    def test_sub_cent_amounts_round_half_up(self) -> None:
        """A $0.005 price becomes 1 cent, not 0."""
        assert Money.from_decimal(Decimal("0.005")).minor_units == 1
        assert Money.from_decimal(Decimal("0.004")).minor_units == 0

    def test_round_trip_through_decimal(self) -> None:
        for raw in ["0.00", "0.01", "9.99", "1234.56"]:
            assert Money.from_decimal(Decimal(raw)).to_decimal() == Decimal(raw)

    def test_float_minor_units_rejected(self) -> None:
        with pytest.raises(MoneyError):
            Money(1.5)  # type: ignore[arg-type]

    def test_bool_is_not_an_int_here(self) -> None:
        with pytest.raises(MoneyError):
            Money(True)

    def test_unsupported_currency_rejected(self) -> None:
        with pytest.raises(UnsupportedCurrencyError):
            Money(100, "XYZ")
        with pytest.raises(UnsupportedCurrencyError):
            Money.from_decimal(Decimal("1"), "XYZ")

    def test_non_finite_rejected(self) -> None:
        with pytest.raises(MoneyError):
            Money.from_decimal(Decimal("NaN"))
        with pytest.raises(MoneyError):
            Money.from_decimal(Decimal("Infinity"))


class TestArithmetic:
    def test_addition_is_exact_over_many_small_amounts(self) -> None:
        """The float trap: 0.1 + 0.2 != 0.3. Integer minor units do not care."""
        cent = Money.from_decimal(Decimal("0.01"))
        result = total([cent] * 100)
        assert result.minor_units == 100
        assert result.to_decimal() == Decimal("1.00")

    def test_realistic_run_total_is_exact(self) -> None:
        """The API_COSTS.md lean run: five searches, tokens, two images, two ops."""
        amounts = [
            Money.from_decimal(Decimal("0.05")),  # 5 web searches
            Money.from_decimal(Decimal("0.002")),  # text input
            Money.from_decimal(Decimal("0.006")),  # text output
            Money.from_decimal(Decimal("0.041")),  # openai image
            Money.from_decimal(Decimal("0.035")),  # recraft image
            Money.from_decimal(Decimal("0.010")),  # background removal
            Money.from_decimal(Decimal("0.004")),  # upscale
        ]
        assert total(amounts).minor_units == 5 + 0 + 1 + 4 + 4 + 1 + 0

    def test_subtraction(self) -> None:
        assert (Money(500) - Money(150)).minor_units == 350

    def test_multiplication_by_int(self) -> None:
        assert (Money(41) * 3).minor_units == 123

    def test_multiplication_by_float_rejected(self) -> None:
        with pytest.raises(MoneyError):
            Money(41) * 1.5  # type: ignore[operator]

    def test_currency_mismatch_rejected(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money(100, "USD") + Money(100, "EUR")
        with pytest.raises(CurrencyMismatchError):
            assert Money(100, "USD") < Money(100, "EUR")

    def test_empty_total_is_zero_not_an_error(self) -> None:
        assert total([]).is_zero

    def test_comparison(self) -> None:
        assert Money(100) > Money(99)
        assert Money(100) >= Money(100)
        assert Money(1) < Money(2)
        assert Money(1) <= Money(1)

    def test_equality_includes_currency(self) -> None:
        assert Money(100, "USD") == Money(100, "USD")
        assert Money(100, "USD") != Money(100, "EUR")


class TestBudgetComparison:
    def test_budget_ceiling_is_exact_at_the_boundary(self) -> None:
        """A run exactly on budget is allowed; one cent over is not."""
        limit = Money.from_decimal(Decimal("1.00"))
        assert Money(100) <= limit
        assert Money(101) > limit

    def test_projected_spend_check(self) -> None:
        spent = Money.from_decimal(Decimal("0.85"))
        projected = Money.from_decimal(Decimal("0.20"))
        limit = Money.from_decimal(Decimal("1.00"))
        assert (spent + projected) > limit


class TestFormatting:
    def test_str_shows_major_units_and_currency(self) -> None:
        assert str(Money(4, "USD")) == "0.04 USD"
        assert str(Money(123456, "GBP")) == "1234.56 GBP"

    def test_negative_amounts_are_representable(self) -> None:
        """Refunds and corrections need to be expressible."""
        assert (Money(100) - Money(150)).minor_units == -50
