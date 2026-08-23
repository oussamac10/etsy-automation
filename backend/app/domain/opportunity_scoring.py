"""Pure domain model and deterministic scoring algorithms for Market Opportunity Discovery.

This module implements the core business logic for evaluating, scoring, and diversifying
commercial design opportunities for Etsy digital PNG products.

No LLM makes arbitrary 0-100 score choices; all scores are calculated deterministically
from evaluated component metrics:
- Demand Signal: 30%
- Competition Opportunity: 20%
- Trend Momentum: 15%
- Seasonal Timing: 15%
- Buyer Intent / Niche Specificity: 10%
- Product Fit: 10%
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class OpportunityType(StrEnum):
    BEST_OPPORTUNITY = "best_opportunity"
    NICHE_OPPORTUNITY = "niche_opportunity"
    EMERGING_OPPORTUNITY = "emerging_opportunity"


class TrendDirection(StrEnum):
    EMERGING = "Emerging"
    RISING = "Rising"
    STABLE = "Stable"
    SEASONAL = "Seasonal"
    DECLINING = "Declining"


class CompetitionClassification(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class MarketValidation(StrEnum):
    STRONG = "Strong"
    MODERATE = "Moderate"
    EMERGING = "Emerging"


class TimingLabel(StrEnum):
    SELL_NOW = "Sell Now"
    PREPARE_NOW = "Prepare Now"
    UPCOMING = "Upcoming"
    EVERGREEN = "Evergreen"
    LATE_AVOID = "Late / Avoid"


# Supported physical products on the platform
SUPPORTED_PRODUCTS = (
    "tshirt",
    "sweatshirt",
    "tote",
    "mug",
    "tumbler",
    "poster",
    "sticker",
    "phone_case",
    "candle",
)

# Product display names and aspect characteristics
PRODUCT_PROFILES: dict[str, dict[str, Any]] = {
    "tshirt": {
        "label": "T-Shirt",
        "optimal_orientation": "vertical",
        "apparel": True,
        "detail_capacity": "medium-high",
    },
    "sweatshirt": {
        "label": "Sweatshirt",
        "optimal_orientation": "vertical",
        "apparel": True,
        "detail_capacity": "medium-high",
    },
    "tote": {
        "label": "Tote Bag",
        "optimal_orientation": "square",
        "apparel": False,
        "detail_capacity": "medium",
    },
    "mug": {
        "label": "Ceramic Mug",
        "optimal_orientation": "centered",
        "apparel": False,
        "detail_capacity": "compact",
        "gift_affinity": 1.2,
    },
    "tumbler": {
        "label": "Tumbler",
        "optimal_orientation": "vertical",
        "apparel": False,
        "detail_capacity": "wrap-around",
    },
    "poster": {
        "label": "Poster",
        "optimal_orientation": "vertical",
        "apparel": False,
        "detail_capacity": "high",
    },
    "sticker": {
        "label": "Sticker",
        "optimal_orientation": "compact",
        "apparel": False,
        "detail_capacity": "bold-contour",
    },
    "phone_case": {
        "label": "Phone Case",
        "optimal_orientation": "vertical",
        "apparel": False,
        "detail_capacity": "centered-tall",
    },
    "candle": {
        "label": "Scented Candle",
        "optimal_orientation": "centered",
        "apparel": False,
        "detail_capacity": "compact-label",
        "gift_affinity": 1.3,
    },
}


@dataclass(frozen=True, slots=True)
class ProductFitScore:
    product: str
    fit: int  # 0 to 100


@dataclass(frozen=True, slots=True)
class OpportunityScores:
    overall: int  # 0 to 100
    demand: int  # 0 to 100
    competition_opportunity: int  # 0 to 100
    trend: int  # 0 to 100
    timing: int  # 0 to 100
    buyer_intent: int  # 0 to 100
    product_fit: int  # 0 to 100

    def to_dict(self) -> dict[str, int]:
        return {
            "overall": self.overall,
            "demand": self.demand,
            "competition_opportunity": self.competition_opportunity,
            "trend": self.trend,
            "timing": self.timing,
            "buyer_intent": self.buyer_intent,
            "product_fit": self.product_fit,
        }


@dataclass(slots=True)
class CandidateOpportunity:
    id: str
    title: str
    concept_summary: str
    target_buyer: str
    niche: str
    season_or_event: str
    visual_direction: str
    design_style: str
    slogan: str | None
    color_palette: list[str]
    keyword_cluster: list[str]
    why_it_could_sell: str
    evidence_summary: list[str]
    # Evaluated raw component signals (0-100)
    demand_signal: int
    competition_signal: int  # 0-100 (where higher means better room to compete / less saturation)
    trend_signal: int
    timing_signal: int
    buyer_intent_signal: int
    # Classification labels
    competition_level: CompetitionClassification
    trend_direction: TrendDirection
    market_validation: MarketValidation
    timing_label: TimingLabel
    recommended_launch_window: str
    ip_risk: str  # "Low", "Review", "High"
    confidence: float  # 0.0 to 1.0 (evidence strength)
    # Computed scores
    recommended_products: list[ProductFitScore] = field(default_factory=list)
    scores: OpportunityScores | None = None
    opportunity_type: OpportunityType = OpportunityType.BEST_OPPORTUNITY
    # Prompt specifications
    positive_prompt: str = ""
    negative_prompt: str = ""
    typography_instructions: str | None = None


def calculate_opportunity_score(
    *,
    demand_score: int,
    competition_opportunity_score: int,
    trend_score: int,
    timing_score: int,
    buyer_intent_score: int,
    product_fit_score: int,
    ip_risk: str = "Low",
) -> OpportunityScores:
    """Deterministically calculate the aggregate commercial opportunity score (0-100).

    Formula:
    Demand: 30%
    Competition Opportunity: 20%
    Trend Momentum: 15%
    Seasonal Timing: 15%
    Buyer Intent / Niche Specificity: 10%
    Product Fit: 10%
    """
    d = max(0, min(100, demand_score))
    c = max(0, min(100, competition_opportunity_score))
    tr = max(0, min(100, trend_score))
    ti = max(0, min(100, timing_score))
    b = max(0, min(100, buyer_intent_score))
    p = max(0, min(100, product_fit_score))

    raw_overall = (d * 0.30) + (c * 0.20) + (tr * 0.15) + (ti * 0.15) + (b * 0.10) + (p * 0.10)

    # Apply IP risk penalty if flagged
    normalized_ip = ip_risk.strip().lower()
    if normalized_ip == "high":
        raw_overall = raw_overall * 0.40  # 60% penalty for high IP risk
    elif normalized_ip in ("review", "medium"):
        raw_overall = raw_overall * 0.85  # 15% penalty for review recommended

    overall = int(round(raw_overall))
    overall = max(0, min(100, overall))

    return OpportunityScores(
        overall=overall,
        demand=d,
        competition_opportunity=c,
        trend=tr,
        timing=ti,
        buyer_intent=b,
        product_fit=p,
    )


def calculate_product_fit_scores(
    *,
    design_style: str,
    visual_direction: str,
    niche: str,
    target_buyer: str,
    intended_product_uses: list[str] | None = None,
) -> list[ProductFitScore]:
    """Calculate fit scores (0-100) across physical products based on layout, gift intent, and aspect."""
    intended = [p.lower().strip() for p in (intended_product_uses or [])]
    style_lower = (design_style + " " + visual_direction).lower()
    buyer_lower = (target_buyer + " " + niche).lower()

    is_apparel_focus = any(
        kw in style_lower for kw in ("oversized", "dtg", "chest", "back print", "distressed")
    )
    is_gift_heavy = any(
        kw in buyer_lower
        for kw in ("mom", "dad", "nurse", "teacher", "coworker", "gift", "friend", "tech")
    )
    is_compact_art = any(
        kw in style_lower
        for kw in ("minimalist", "kawaii", "sticker", "badge", "centered", "clean")
    )

    scores: list[ProductFitScore] = []

    for prod_key in SUPPORTED_PRODUCTS:
        base_score = 75

        if prod_key in ("tshirt", "sweatshirt"):
            if is_apparel_focus:
                base_score += 18
            else:
                base_score += 10
        elif prod_key in ("mug", "tumbler", "candle"):
            if is_gift_heavy or is_compact_art:
                base_score += 19
            else:
                base_score += 8
        elif prod_key in ("sticker", "phone_case"):
            if is_compact_art or "sticker" in style_lower:
                base_score += 20
            else:
                base_score += 5
        elif prod_key in ("tote", "poster"):
            if not is_apparel_focus:
                base_score += 12

        # Intended product boost if explicitly requested by campaign
        if prod_key in intended:
            base_score = max(base_score, 88)
            base_score = min(100, base_score + 8)

        fit = max(40, min(100, base_score))
        scores.append(ProductFitScore(product=prod_key, fit=fit))

    # Sort descending by fit score
    scores.sort(key=lambda s: s.fit, reverse=True)
    return scores


def calculate_seasonal_timing(
    season_or_event: str,
    target_country: str = "US",
    now: datetime | None = None,
) -> tuple[TimingLabel, str, int]:
    """Calculate practical seasonal lead-time (30-120 days ahead) for target marketplace country.

    Returns:
        (TimingLabel, recommended_launch_window, timing_score_0_to_100)
    """
    current_moment = now or datetime.now(UTC)
    current_month = current_moment.month  # 1 to 12
    country = target_country.upper().strip()

    event_lower = season_or_event.lower().strip()

    # Evergreen / Non-seasonal concepts
    if any(
        kw in event_lower
        for kw in ("evergreen", "year-round", "everyday", "no special", "all season")
    ):
        return TimingLabel.EVERGREEN, "Year-Round", 85

    # Season / Event Peak Month Mappings (Northern Hemisphere default)
    # Lead time is optimal when discovering/designing 1 to 3 months (30-120 days) before peak.
    event_peaks: dict[str, tuple[int, int]] = {  # (peak_month, prep_start_month)
        "halloween": (10, 7),  # Peak Oct, Prep starts Jul-Aug
        "fall": (10, 7),
        "autumn": (10, 7),
        "thanksgiving": (11, 8),
        "christmas": (12, 9),  # Peak Dec, Prep starts Sep-Oct
        "holiday": (12, 9),
        "winter": (1, 10),
        "valentines": (2, 11),  # Peak Feb, Prep starts Nov-Dec
        "st patrick": (3, 1),
        "easter": (4, 2),
        "spring": (4, 2),
        "mothers day": (
            5 if country in ("US", "CA", "DE", "FR", "AU") else 3,
            2,
        ),  # UK Mother's Day is March
        "fathers day": (6 if country != "AU" else 9, 4),  # Australia Father's Day is Sept
        "graduation": (5, 3),
        "summer": (7, 4),
        "back to school": (8, 6),
    }

    matched_peak: tuple[int, int] | None = None
    for name, (peak, prep) in event_peaks.items():
        if name in event_lower:
            matched_peak = (peak, prep)
            break

    if not matched_peak:
        return TimingLabel.EVERGREEN, "Flexible Window", 78

    peak_month, prep_month = matched_peak

    # Calculate month difference forward (0 to 11)
    month_diff = (peak_month - current_month) % 12

    # Month Names helper
    month_names = [
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    prep_name = month_names[prep_month]
    peak_name = month_names[peak_month]
    launch_window = f"{prep_name}–{peak_name}"

    if month_diff == 0:
        # Peak month right now
        return TimingLabel.SELL_NOW, f"Immediate ({peak_name})", 95
    elif month_diff in (1, 2, 3):
        # 30-90 days ahead: Perfect prepare now window
        return TimingLabel.PREPARE_NOW, launch_window, 98
    elif month_diff in (4, 5):
        # 120-150 days ahead: Upcoming
        return TimingLabel.UPCOMING, launch_window, 75
    elif month_diff in (6, 7, 8):
        # 6+ months away: Early / Low urgency
        return TimingLabel.UPCOMING, launch_window, 60
    else:
        # Just passed peak: Late / Avoid for current cycle
        return TimingLabel.LATE_AVOID, f"Post-Season ({launch_window})", 35


def filter_and_diversify_opportunities(
    candidates: list[CandidateOpportunity],
    count: int = 3,
) -> list[CandidateOpportunity]:
    """Apply semantic diversity filtering and assign the 3 distinct opportunity archetypes.

    Deduplicates candidates with overlapping keywords, target buyers, and visual angles.
    Selects:
    1. BEST_OPPORTUNITY (Highest balanced commercial score)
    2. NICHE_OPPORTUNITY (High buyer specificity / lowest competition in sub-niche)
    3. EMERGING_OPPORTUNITY (High trend momentum / upcoming timing)
    """
    if len(candidates) <= count:
        types = [
            OpportunityType.BEST_OPPORTUNITY,
            OpportunityType.NICHE_OPPORTUNITY,
            OpportunityType.EMERGING_OPPORTUNITY,
        ]
        for idx, c in enumerate(candidates):
            c.opportunity_type = types[min(idx, len(types) - 1)]
        return candidates

    sorted_candidates = sorted(
        candidates,
        key=lambda c: c.scores.overall if c.scores else 0,
        reverse=True,
    )

    selected: list[CandidateOpportunity] = []

    def _is_too_similar(c1: CandidateOpportunity, c2: CandidateOpportunity) -> bool:
        b1 = set(c1.target_buyer.lower().split())
        b2 = set(c2.target_buyer.lower().split())
        buyer_overlap = len(b1.intersection(b2)) / max(1, min(len(b1), len(b2)))

        n1 = set(c1.niche.lower().split())
        n2 = set(c2.niche.lower().split())
        niche_overlap = len(n1.intersection(n2)) / max(1, min(len(n1), len(n2)))

        return buyer_overlap > 0.6 and niche_overlap > 0.6

    # 1. Select Best Opportunity (Top overall score)
    best_candidate = sorted_candidates[0]
    best_candidate.opportunity_type = OpportunityType.BEST_OPPORTUNITY
    selected.append(best_candidate)

    # 2. Select Niche Opportunity (Highest buyer clarity & competition opportunity distinct from Best)
    remaining = [c for c in sorted_candidates if c.id != best_candidate.id]
    niche_candidates = sorted(
        remaining,
        key=lambda c: c.buyer_intent_signal * 0.5 + c.competition_signal * 0.5,
        reverse=True,
    )
    niche_candidate = None
    for cand in niche_candidates:
        if not _is_too_similar(cand, best_candidate):
            niche_candidate = cand
            break
    if not niche_candidate and niche_candidates:
        niche_candidate = niche_candidates[0]

    if niche_candidate:
        niche_candidate.opportunity_type = OpportunityType.NICHE_OPPORTUNITY
        selected.append(niche_candidate)

    # 3. Select Emerging Opportunity (Highest trend & timing signal distinct from selected)
    remaining_emerging = [
        c for c in remaining if c.id != (niche_candidate.id if niche_candidate else "")
    ]
    emerging_candidates = sorted(
        remaining_emerging,
        key=lambda c: c.trend_signal * 0.6 + c.timing_signal * 0.4,
        reverse=True,
    )
    emerging_candidate = None
    for cand in emerging_candidates:
        if not any(_is_too_similar(cand, s) for s in selected):
            emerging_candidate = cand
            break
    if not emerging_candidate and emerging_candidates:
        emerging_candidate = emerging_candidates[0]

    if emerging_candidate:
        emerging_candidate.opportunity_type = OpportunityType.EMERGING_OPPORTUNITY
        selected.append(emerging_candidate)

    # Fallback to make sure we return exactly count items
    while len(selected) < count and len(sorted_candidates) > len(selected):
        for c in sorted_candidates:
            if c not in selected:
                selected.append(c)
                break

    return selected[:count]
