"""Market Opportunity Discovery Application Service.

Coordinates candidate generation (10-20 concepts), multi-signal evaluation,
IP pre-screening, deterministic scoring, and diversity filtering.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.opportunity_scoring import (
    CandidateOpportunity,
    CompetitionClassification,
    MarketValidation,
    OpportunityScores,
    OpportunityType,
    ProductFitScore,
    TimingLabel,
    TrendDirection,
    calculate_opportunity_score,
    calculate_product_fit_scores,
    calculate_seasonal_timing,
    filter_and_diversify_opportunities,
)
from app.domain.workflow import RiskLevel
from app.ports.providers import (
    ResearchProvider,
    SearchQuery,
    SearchResult,
    TextGenerationProvider,
    TextRequest,
)

logger = logging.getLogger("app.application.market_discovery")


DISCOVERY_SYSTEM_PROMPT = """You are an expert Market Opportunity Discovery Engine for Etsy digital PNG products.
Your mission is to answer: "What should I design next that has a realistic commercial chance to sell?"

Core Principle:
Do NOT copy Etsy best sellers. Use best sellers and proven patterns strictly as EVIDENCE of demand.
Identify under-served angles, rising trends, specific high-intent buyers, and timely seasonal opportunities.

You must generate a pool of 10 to 20 DISTINCT candidate opportunities.
Output MUST be a valid JSON object following this exact JSON structure:
{
  "confidence": 0.85,
  "confidence_explanation": "Strong multi-source evidence across healthcare and seasonal niches",
  "proven_market_observations": [
    "High demand for profession-specific holiday apparel",
    "Retro groovy and kawaii aesthetics show strong repeat purchase signals"
  ],
  "candidates": [
    {
      "id": "cand-1",
      "title": "Retro Radiology Halloween Crew",
      "concept_summary": "Hand-drawn retro kawaii skeleton and x-ray illustration designed for radiology tech Halloween shirts and mugs.",
      "target_buyer": "Radiology Technologists & X-Ray Technicians",
      "niche": "Healthcare / Radiology",
      "season_or_event": "Halloween",
      "visual_direction": "Vintage 70s pastel distressed illustration with cute smiling skeleton and bones",
      "design_style": "Retro Groovy Kawaii",
      "slogan": null,
      "color_palette": ["#E07A5F", "#3D405B", "#81B29A", "#F2CC8F", "#F4F1DE"],
      "keyword_cluster": [
        "radiology halloween png",
        "rad tech shirt design",
        "xray technician gift",
        "cute skeleton sublimation"
      ],
      "why_it_could_sell": "Combines proven healthcare Halloween seasonal demand with a highly specific radiology buyer group, avoiding saturated general nurse designs.",
      "evidence_summary": [
        "Strong seasonal search intent for healthcare Halloween gifts",
        "Low saturation compared to general RN listings"
      ],
      "demand_signal": 92,
      "competition_signal": 78,
      "trend_signal": 86,
      "buyer_intent_signal": 94,
      "competition_level": "Medium",
      "trend_direction": "Rising",
      "market_validation": "Strong",
      "ip_risk": "Low",
      "prompt": {
        "positive_prompt": "Retro 70s kawaii style illustration of a cute smiling skeleton holding an x-ray film, surrounded by retro flowers and autumn pumpkins, soft pastel distressed texture, isolated central artwork on a transparent background, clean uncropped edges, high resolution",
        "negative_prompt": "background, scene, photo, realistic human, watermark, signature, blurry edges, cropped design",
        "typography_instructions": null,
        "exact_slogan": null
      }
    }
  ]
}

Rules to strictly follow:
1. Generate between 10 and 20 candidate opportunities with distinct angles, niches, buyer groups, and styles.
2. NEVER invent exact numeric search numbers (e.g. do not say '12,400 monthly searches'). Use qualitative signals and 0-100 relative signal ratings.
3. Every prompt MUST specify 'isolated central artwork on a transparent background' and 'clean uncropped edges'.
4. Keep slogans null or separate from the positive visual prompt.
5. Provide actionable 'why_it_could_sell' rationales based on market dynamics.
"""


class MarketOpportunityDiscoveryService:
    def __init__(
        self,
        search_provider: ResearchProvider,
        text_provider: TextGenerationProvider,
    ) -> None:
        self.search_provider = search_provider
        self.text_provider = text_provider

    async def run_market_scan(
        self,
        *,
        target_country: str,
        output_language: str,
        preferred_niche: list[str] | None = None,
        target_buyer: list[str] | None = None,
        intended_products: list[str] | None = None,
        desired_styles: list[str] | None = None,
        occasions: list[str] | None = None,
        seasons: list[str] | None = None,
    ) -> list[tuple[str, str, SearchResult]]:
        """Run multi-angle search query scan across broad, long-tail, buyer, style, and product queries."""
        niche_text = ", ".join(preferred_niche) if preferred_niche else "trending Etsy digital PNG"
        buyer_text = ", ".join(target_buyer) if target_buyer else "gift buyers"
        style_text = ", ".join(desired_styles) if desired_styles else "retro watercolor cute"
        product_text = ", ".join(intended_products) if intended_products else "tshirt mug sticker"
        occasion_text = ", ".join(occasions or seasons or ["upcoming season"])

        angles = {
            "demand": f"{niche_text} png clipart digital download {target_country}",
            "best_seller_patterns": f"best selling {niche_text} png sublimation designs",
            "underserved_niche": f"{buyer_text} {niche_text} {occasion_text} transparent png",
            "trend_momentum": f"trending {style_text} design trends {target_country} png",
            "product_fit": f"{niche_text} design for {product_text}",
        }

        evidence_list: list[tuple[str, str, SearchResult]] = []
        for angle_name, query_text in angles.items():
            try:
                results = await self.search_provider.search(
                    SearchQuery(text=query_text, angle=angle_name)
                )
                for res in results:
                    evidence_list.append((angle_name, query_text, res))
            except Exception as exc:
                logger.warning(
                    "search_scan_angle_failed",
                    extra={"angle": angle_name, "query": query_text, "error": str(exc)},
                )

        return evidence_list

    async def discover_opportunities(
        self,
        *,
        target_country: str,
        output_language: str,
        intended_products: list[str],
        preferred_niche: list[str] | None = None,
        target_buyer: list[str] | None = None,
        desired_styles: list[str] | None = None,
        occasions: list[str] | None = None,
        seasons: list[str] | None = None,
        evidence_list: list[tuple[str, str, SearchResult]] | None = None,
        now: datetime | None = None,
    ) -> tuple[list[CandidateOpportunity], list[CandidateOpportunity], float, list[str]]:
        """Run full opportunity generation pipeline.

        Returns:
            (top_3_diversified_opportunities, all_scored_candidates, confidence_score, proven_market_observations)
        """
        current_moment = now or datetime.now(UTC)

        # 1. Gather research evidence if not provided
        if not evidence_list:
            evidence_list = await self.run_market_scan(
                target_country=target_country,
                output_language=output_language,
                preferred_niche=preferred_niche,
                target_buyer=target_buyer,
                intended_products=intended_products,
                desired_styles=desired_styles,
                occasions=occasions,
                seasons=seasons,
            )

        evidence_text = "\n".join(
            [
                f"[{angle.upper()}] {res.title} ({res.url}): {res.observation}"
                for angle, _, res in evidence_list
            ]
        )

        user_prompt = (
            f"Target Marketplace Country: {target_country}\n"
            f"Output Language: {output_language}\n"
            f"Intended Physical Products: {', '.join(intended_products)}\n"
            f"Preferred Niche: {', '.join(preferred_niche) if preferred_niche else 'Broad Discovery (Find promising niches)'}\n"
            f"Target Buyer Persona: {', '.join(target_buyer) if target_buyer else 'Discover from market signals'}\n"
            f"Desired Styles: {', '.join(desired_styles) if desired_styles else 'Explore top performing styles'}\n"
            f"Occasion / Season: {', '.join(occasions or seasons or ['Upcoming 30-120 days'])}"
            f"\n\nGathered Market Evidence:\n{evidence_text}\n"
        )

        # 2. Call Text Generation Provider for Candidate Pool
        response = await self.text_provider.generate(
            TextRequest(
                prompt=user_prompt,
                system=DISCOVERY_SYSTEM_PROMPT,
                max_output_tokens=8192,
            )
        )

        try:
            payload = json.loads(response.text)
        except Exception:
            # Fallback if json extraction needed
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match:
                payload = json.loads(match.group(0))
            else:
                raise ValueError("Failed to parse structured JSON from text provider.")

        confidence = float(payload.get("confidence", 0.80))
        proven_observations = payload.get("proven_market_observations", [])
        raw_candidates = payload.get("candidates", [])

        # 3. Process, Score, and Evaluate each candidate deterministically
        candidate_objects: list[CandidateOpportunity] = []

        for idx, raw in enumerate(raw_candidates):
            cid = str(raw.get("id") or f"cand-{idx + 1}")
            title = str(raw.get("title", f"Design Opportunity {idx + 1}"))
            summary = str(raw.get("concept_summary", ""))
            buyer = str(raw.get("target_buyer", "General Gift Buyers"))
            niche = str(raw.get("niche", "General"))
            season_event = str(raw.get("season_or_event", "Evergreen"))
            visual_dir = str(raw.get("visual_direction", "Clean illustration on transparent background"))
            style = str(raw.get("design_style", "Modern Illustration"))
            slogan = raw.get("slogan")
            palette = list(raw.get("color_palette", []))
            keywords = list(raw.get("keyword_cluster", []))
            why_sell = str(raw.get("why_it_could_sell", "Proven buyer interest and room for differentiation."))
            evidence_sum = list(raw.get("evidence_summary", []))

            demand_sig = int(raw.get("demand_signal", 80))
            comp_sig = int(raw.get("competition_signal", 75))
            trend_sig = int(raw.get("trend_signal", 80))
            buyer_sig = int(raw.get("buyer_intent_signal", 85))

            # Seasonal Timing calculation (30-120 days ahead)
            timing_label, launch_window, timing_score = calculate_seasonal_timing(
                season_event,
                target_country=target_country,
                now=current_moment,
            )

            # Product Fit calculation
            product_fits = calculate_product_fit_scores(
                design_style=style,
                visual_direction=visual_dir,
                niche=niche,
                target_buyer=buyer,
                intended_product_uses=intended_products,
            )
            # Find average product fit for the requested intended products
            matching_fits = [
                pf.fit for pf in product_fits if pf.product.lower() in [p.lower() for p in intended_products]
            ]
            product_fit_score = int(sum(matching_fits) / max(1, len(matching_fits))) if matching_fits else product_fits[0].fit

            ip_risk_str = str(raw.get("ip_risk", "Low")).title()

            # Deterministic Score Calculation
            scores = calculate_opportunity_score(
                demand_score=demand_sig,
                competition_opportunity_score=comp_sig,
                trend_score=trend_sig,
                timing_score=timing_score,
                buyer_intent_score=buyer_sig,
                product_fit_score=product_fit_score,
                ip_risk=ip_risk_str,
            )

            comp_level_str = str(raw.get("competition_level", "Medium")).title()
            comp_level = CompetitionClassification.MEDIUM
            if comp_level_str in ("Low", "High"):
                comp_level = CompetitionClassification(comp_level_str)

            trend_dir_str = str(raw.get("trend_direction", "Rising")).title()
            trend_dir = TrendDirection.RISING
            for td in TrendDirection:
                if td.value.lower() == trend_dir_str.lower():
                    trend_dir = td
                    break

            market_val_str = str(raw.get("market_validation", "Strong")).title()
            market_val = MarketValidation.STRONG
            for mv in MarketValidation:
                if mv.value.lower() == market_val_str.lower():
                    market_val = mv
                    break

            prompt_dict = raw.get("prompt", {})
            pos_prompt = str(prompt_dict.get("positive_prompt", f"{visual_dir}, isolated central artwork on a transparent background, clean uncropped edges"))
            neg_prompt = str(prompt_dict.get("negative_prompt", "background, scene, photo, watermark, signature, cropped"))
            typo_instr = prompt_dict.get("typography_instructions")

            cand = CandidateOpportunity(
                id=cid,
                title=title,
                concept_summary=summary,
                target_buyer=buyer,
                niche=niche,
                season_or_event=season_event,
                visual_direction=visual_dir,
                design_style=style,
                slogan=slogan,
                color_palette=palette,
                keyword_cluster=keywords,
                why_it_could_sell=why_sell,
                evidence_summary=evidence_sum,
                demand_signal=demand_sig,
                competition_signal=comp_sig,
                trend_signal=trend_sig,
                timing_signal=timing_score,
                buyer_intent_signal=buyer_sig,
                competition_level=comp_level,
                trend_direction=trend_dir,
                market_validation=market_val,
                timing_label=timing_label,
                recommended_launch_window=launch_window,
                ip_risk=ip_risk_str,
                confidence=confidence,
                recommended_products=product_fits,
                scores=scores,
                positive_prompt=pos_prompt,
                negative_prompt=neg_prompt,
                typography_instructions=typo_instr,
            )
            candidate_objects.append(cand)

        # 4. Diversity Filter & Final 3 Selection
        top_3 = filter_and_diversify_opportunities(candidate_objects, count=3)

        return top_3, candidate_objects, confidence, proven_observations

    def select_refresh_candidate(
        self,
        candidate_pool: list[CandidateOpportunity],
        current_active_concepts: list[CandidateOpportunity],
        concept_to_replace_id: str,
    ) -> CandidateOpportunity | None:
        """Select a replacement concept from candidate pool that does not duplicate remaining active concepts."""
        active_remaining = [c for c in current_active_concepts if c.id != concept_to_replace_id]

        def _is_similar(c1: CandidateOpportunity, c2: CandidateOpportunity) -> bool:
            b1 = set(c1.target_buyer.lower().split())
            b2 = set(c2.target_buyer.lower().split())
            n1 = set(c1.niche.lower().split())
            n2 = set(c2.niche.lower().split())
            return (len(b1.intersection(b2)) > 0 and len(n1.intersection(n2)) > 0)

        active_ids = {c.id for c in current_active_concepts}

        # Filter candidates not currently active
        available = [c for c in candidate_pool if c.id not in active_ids]
        if not available:
            return None

        # Sort by overall score
        available.sort(key=lambda c: c.scores.overall if c.scores else 0, reverse=True)

        for cand in available:
            if not any(_is_similar(cand, act) for act in active_remaining):
                return cand

        # Fallback to top available
        return available[0]
