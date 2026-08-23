"""Unit tests for Market Opportunity Discovery scoring, diversity filtering, and product fit."""

from datetime import UTC, datetime

from app.domain.opportunity_scoring import (
    CandidateOpportunity,
    CompetitionClassification,
    MarketValidation,
    OpportunityType,
    TimingLabel,
    TrendDirection,
    calculate_opportunity_score,
    calculate_product_fit_scores,
    calculate_seasonal_timing,
    filter_and_diversify_opportunities,
)


def test_deterministic_scoring_formula():
    # Demand 30%, Competition 20%, Trend 15%, Timing 15%, Buyer 10%, Product Fit 10%
    # Overall = 90*0.30 + 80*0.20 + 70*0.15 + 60*0.15 + 50*0.10 + 40*0.10
    # = 27 + 16 + 10.5 + 9 + 5 + 4 = 71.5 -> 72
    scores = calculate_opportunity_score(
        demand_score=90,
        competition_opportunity_score=80,
        trend_score=70,
        timing_score=60,
        buyer_intent_score=50,
        product_fit_score=40,
        ip_risk="Low",
    )
    assert scores.overall == 72
    assert scores.demand == 90
    assert scores.competition_opportunity == 80
    assert scores.trend == 70
    assert scores.timing == 60
    assert scores.buyer_intent == 50
    assert scores.product_fit == 40


def test_ip_risk_penalty_applied():
    # High risk should receive 60% penalty (0.40 multiplier)
    scores_low = calculate_opportunity_score(
        demand_score=100,
        competition_opportunity_score=100,
        trend_score=100,
        timing_score=100,
        buyer_intent_score=100,
        product_fit_score=100,
        ip_risk="Low",
    )
    assert scores_low.overall == 100

    scores_high = calculate_opportunity_score(
        demand_score=100,
        competition_opportunity_score=100,
        trend_score=100,
        timing_score=100,
        buyer_intent_score=100,
        product_fit_score=100,
        ip_risk="High",
    )
    assert scores_high.overall == 40

    scores_review = calculate_opportunity_score(
        demand_score=100,
        competition_opportunity_score=100,
        trend_score=100,
        timing_score=100,
        buyer_intent_score=100,
        product_fit_score=100,
        ip_risk="Review",
    )
    assert scores_review.overall == 85


def test_product_fit_scores():
    # Ceramic mug & candle should have high fit for gift/compact niches
    mug_fits = calculate_product_fit_scores(
        design_style="Cozy Watercolor",
        visual_direction="Cute centered badge illustration",
        niche="Healthcare / Nurse",
        target_buyer="Nurse Coworker Gift",
        intended_product_uses=["mug"],
    )
    mug_item = next(f for f in mug_fits if f.product == "mug")
    assert mug_item.fit >= 88

    # T-shirt / sweatshirt should have high fit for DTG apparel styles
    apparel_fits = calculate_product_fit_scores(
        design_style="Vintage 70s Distressed",
        visual_direction="Oversized back print graphic DTG",
        niche="Outdoors / Camping",
        target_buyer="Hikers & Campers",
        intended_product_uses=["tshirt", "sweatshirt"],
    )
    tshirt_item = next(f for f in apparel_fits if f.product == "tshirt")
    assert tshirt_item.fit >= 88


def test_seasonal_timing_lookahead():
    # When current month is August (8), Halloween (October 10) is 2 months ahead (30-90 days): PREPARE_NOW
    august_moment = datetime(2026, 8, 15, tzinfo=UTC)
    label, window, score = calculate_seasonal_timing(
        season_or_event="Halloween",
        target_country="US",
        now=august_moment,
    )
    assert label == TimingLabel.PREPARE_NOW
    assert "October" in window
    assert score >= 90

    # Evergreen concept
    label_eg, window_eg, score_eg = calculate_seasonal_timing(
        season_or_event="Evergreen",
        target_country="US",
        now=august_moment,
    )
    assert label_eg == TimingLabel.EVERGREEN
    assert score_eg >= 80


def test_filter_and_diversify_opportunities():
    # Create 6 candidates with varying scores and niches
    c1 = CandidateOpportunity(
        id="c1",
        title="Top General Halloween Design",
        concept_summary="Halloween ghost",
        target_buyer="General Shoppers",
        niche="Halloween",
        season_or_event="Halloween",
        visual_direction="Retro ghost",
        design_style="Retro 70s",
        slogan=None,
        color_palette=["#000", "#FFF"],
        keyword_cluster=["halloween png"],
        why_it_could_sell="High seasonal volume",
        evidence_summary=[],
        demand_signal=95,
        competition_signal=70,
        trend_signal=90,
        timing_signal=95,
        buyer_intent_signal=80,
        competition_level=CompetitionClassification.MEDIUM,
        trend_direction=TrendDirection.RISING,
        market_validation=MarketValidation.STRONG,
        timing_label=TimingLabel.PREPARE_NOW,
        recommended_launch_window="August–October",
        ip_risk="Low",
        confidence=0.9,
    )
    c1.scores = calculate_opportunity_score(
        demand_score=95,
        competition_opportunity_score=70,
        trend_score=90,
        timing_score=95,
        buyer_intent_score=80,
        product_fit_score=90,
    )

    c2 = CandidateOpportunity(
        id="c2",
        title="Radiology Tech Halloween Skeletons",
        concept_summary="Skeleton with xray",
        target_buyer="Radiology Technicians",
        niche="Healthcare / Radiology",
        season_or_event="Halloween",
        visual_direction="Kawaii bones",
        design_style="Pastel Kawaii",
        slogan=None,
        color_palette=["#000", "#FFF"],
        keyword_cluster=["rad tech halloween"],
        why_it_could_sell="Specific buyer sub-niche",
        evidence_summary=[],
        demand_signal=88,
        competition_signal=92,
        trend_signal=85,
        timing_signal=95,
        buyer_intent_signal=98,
        competition_level=CompetitionClassification.LOW,
        trend_direction=TrendDirection.RISING,
        market_validation=MarketValidation.STRONG,
        timing_label=TimingLabel.PREPARE_NOW,
        recommended_launch_window="August–October",
        ip_risk="Low",
        confidence=0.9,
    )
    c2.scores = calculate_opportunity_score(
        demand_score=88,
        competition_opportunity_score=92,
        trend_score=85,
        timing_score=95,
        buyer_intent_score=98,
        product_fit_score=90,
    )

    c3 = CandidateOpportunity(
        id="c3",
        title="Emerging Celestial Cat Stargazer",
        concept_summary="Cat under crescent moon",
        target_buyer="Cat Lovers & Astrologers",
        niche="Celestial / Pets",
        season_or_event="Evergreen",
        visual_direction="Midnight Indigo celestial",
        design_style="Celestial Line Art",
        slogan=None,
        color_palette=["#000", "#FFF"],
        keyword_cluster=["celestial cat png"],
        why_it_could_sell="Fast rising aesthetic crossover",
        evidence_summary=[],
        demand_signal=82,
        competition_signal=85,
        trend_signal=96,
        timing_signal=85,
        buyer_intent_signal=88,
        competition_level=CompetitionClassification.LOW,
        trend_direction=TrendDirection.EMERGING,
        market_validation=MarketValidation.MODERATE,
        timing_label=TimingLabel.EVERGREEN,
        recommended_launch_window="Year-Round",
        ip_risk="Low",
        confidence=0.85,
    )
    c3.scores = calculate_opportunity_score(
        demand_score=82,
        competition_opportunity_score=85,
        trend_score=96,
        timing_score=85,
        buyer_intent_score=88,
        product_fit_score=85,
    )

    top_3 = filter_and_diversify_opportunities([c1, c2, c3], count=3)
    assert len(top_3) == 3
    types = {c.opportunity_type for c in top_3}
    assert OpportunityType.BEST_OPPORTUNITY in types
    assert OpportunityType.NICHE_OPPORTUNITY in types
    assert OpportunityType.EMERGING_OPPORTUNITY in types
