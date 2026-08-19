"""Tests for Phase 9 pricing domain and recommendation logic."""

import pytest
from app.domain.pricing import (
    calculate_price_recommendation,
    format_currency_amount,
    validate_price_minor_units,
)


class TestPricingDomain:
    def test_format_currency_amount(self):
        assert format_currency_amount(499, "USD") == "$4.99"
        assert format_currency_amount(550, "EUR") == "€5.50"
        assert format_currency_amount(450, "GBP") == "£4.50"
        assert format_currency_amount(499, "CAD") == "CA$4.99"

    def test_valid_price_minor_units(self):
        valid, err = validate_price_minor_units(499, "USD")
        assert valid is True
        assert err is None

    def test_invalid_price_zero_or_none(self):
        valid, err = validate_price_minor_units(0, "USD")
        assert valid is False
        assert "greater than zero" in (err or "")

        valid, err = validate_price_minor_units(None, "USD")
        assert valid is False
        assert "is required" in (err or "")

    def test_invalid_price_below_etsy_minimum(self):
        valid, err = validate_price_minor_units(10, "USD")  # 10 cents is below 20 cents
        assert valid is False
        assert "lower than Etsy minimum" in (err or "")

    def test_invalid_price_above_etsy_maximum(self):
        valid, err = validate_price_minor_units(6000000, "USD")  # $60,000
        assert valid is False
        assert "exceeds safety limit" in (err or "")


class TestPricingRecommendationEngine:
    def test_recommendation_with_bundle_design(self):
        rec = calculate_price_recommendation(
            title="Vintage Christmas Sublimation Bundle PNG Clipart",
            tags=["retro sublimation bundle", "christmas png pack", "vintage clipart"],
            currency="USD",
        )
        assert rec.recommended_minor_units >= 499
        assert rec.currency == "USD"
        assert "$4.99" in rec.formatted_price or "$6.99" in rec.formatted_price
        assert len(rec.factors) > 0

    def test_recommendation_eur_shop(self):
        rec = calculate_price_recommendation(
            title="Cute Fall Baking PNG Design",
            tags=["fall baking png", "cute aesthetic pumpkin"],
            currency="EUR",
        )
        assert rec.currency == "EUR"
        assert "€" in rec.formatted_price
        assert rec.recommended_minor_units in (399, 449, 499, 549)
