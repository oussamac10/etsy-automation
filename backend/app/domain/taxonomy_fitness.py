"""Taxonomy Fitness Evaluation Engine.

Evaluates compatibility between an Etsy seller taxonomy node (including its live
Etsy-supported properties and allowed values) and the current campaign context.
Strictly relies on real Etsy properties without inventing fake values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Sequence

from app.ports.providers import EtsyTaxonomyNode, EtsyTaxonomyProperty


@dataclass(frozen=True, slots=True)
class TaxonomyFitResult:
    score: float  # 0.0 to 1.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_mismatched_required_attributes: bool = False
    mismatched_required_reason: str | None = None


# Disqualified physical category path keywords
DISQUALIFIED_PHYSICAL_KEYWORDS = frozenset(
    [
        "plates",
        "plate",
        "kitchen",
        "dining",
        "cutlery",
        "drinkware",
        "mugs",
        "mug",
        "tumbler",
        "clothing",
        "t-shirt",
        "t-shirts",
        "tops & tees",
        "hoodies",
        "shoes",
        "jewelry",
        "furniture",
        "lighting",
        "bags & purses",
        "costumes",
    ]
)

# Semantic craft value groups
SUBLIMATION_PRINTING_CRAFT_VALUES = frozenset(
    [
        "sublimation",
        "printing & printmaking",
        "printing",
        "fabric printing",
        "heat transfer",
        "apparel",
        "digital design",
        "graphic design",
        "dtg",
        "t-shirt printing",
        "screen printing",
        "iron on",
    ]
)

PAPER_ONLY_CRAFT_VALUES = frozenset(
    [
        "card making & stationery",
        "card making",
        "collage",
        "kids' crafts",
        "kids crafts",
        "scrapbooking",
        "origami",
        "papercraft",
        "paper craft",
        "stationery",
        "junk journal",
    ]
)


def _extract_campaign_tokens(campaign_context: dict[str, Any]) -> set[str]:
    """Combine and tokenize all campaign text fields."""
    parts: list[str] = []
    for key in (
        "title",
        "description",
        "product_type",
        "slogan",
        "approved_concept",
        "concept",
    ):
        val = campaign_context.get(key)
        if val and isinstance(val, str):
            parts.append(val)

    tags = campaign_context.get("tags")
    if tags and isinstance(tags, (list, tuple)):
        parts.extend([str(t) for t in tags])

    intended_uses = campaign_context.get("intended_product_uses")
    if intended_uses and isinstance(intended_uses, (list, tuple)):
        parts.extend([str(u).replace("_", " ") for u in intended_uses])

    combined = " ".join(parts).lower()
    return set(re.findall(r"\b[a-z0-9_-]+\b", combined))


def is_physical_disqualified(path: str) -> bool:
    """Check if a taxonomy path clearly represents a physical product."""
    clean = path.lower()
    if (
        clean.startswith("home & living")
        or clean.startswith("clothing")
        or clean.startswith("kitchen")
    ):
        return True
    tokens = set(re.findall(r"\b[a-z-]+\b", clean))
    return bool(tokens & DISQUALIFIED_PHYSICAL_KEYWORDS)


def evaluate_taxonomy_fit(
    *,
    taxonomy_node: EtsyTaxonomyNode,
    taxonomy_properties: Sequence[EtsyTaxonomyProperty],
    campaign_context: dict[str, Any],
) -> TaxonomyFitResult:
    """Evaluate fitness of an Etsy taxonomy category against campaign context.

    Evaluates both path relevance and real property definitions/allowed values.
    """
    path_lower = taxonomy_node.full_path.lower()
    name_lower = taxonomy_node.name.lower()

    # 1. Disqualify physical product categories
    if is_physical_disqualified(taxonomy_node.full_path):
        return TaxonomyFitResult(
            score=0.0,
            warnings=["Physical product category is disqualified for digital products."],
            has_mismatched_required_attributes=True,
            mismatched_required_reason="Physical product category cannot be used for digital downloads.",
        )

    tokens = _extract_campaign_tokens(campaign_context)

    # Detect campaign intent
    is_scrapbooking_paper = any(
        k in tokens
        for k in (
            "scrapbook",
            "scrapbooking",
            "card making",
            "stationery",
            "junk journal",
            "paper craft",
            "planner",
            "origami",
            "ephemera",
        )
    )

    is_sublimation_apparel = any(
        k in tokens
        for k in (
            "sublimation",
            "shirt",
            "t-shirt",
            "tshirt",
            "sweatshirt",
            "hoodie",
            "mug",
            "tumbler",
            "dtg",
            "pod",
            "heat transfer",
            "fabric",
            "apparel",
            "iron on",
            "print on demand",
        )
    )

    is_wall_art_print = (
        campaign_context.get("product_type") == "digital_print"
        or any(
            k in tokens
            for k in (
                "wall art",
                "poster",
                "print",
                "digital print",
                "printable wall art",
                "nursery art",
                "decor",
            )
        )
    )

    is_illustration = (
        campaign_context.get("product_type") == "digital_drawing"
        or any(
            k in tokens
            for k in (
                "illustration",
                "drawing",
                "portrait",
                "sketch",
                "hand drawn",
                "line art",
                "digital illustration",
            )
        )
    )

    score = 40.0  # Base score for valid digital node
    reasons: list[str] = ["Digital download compatible"]
    warnings: list[str] = []
    has_mismatched_required = False
    mismatched_reason: str | None = None

    # 2. Path relevance with intent weighting
    if is_illustration and ("drawing & illustration" in path_lower or "digital" in path_lower and "drawing" in path_lower):
        score += 45.0
        reasons.append("Optimized for digital drawing & illustration")
    elif is_wall_art_print and ("prints > digital prints" in path_lower or "prints" in path_lower):
        score += 45.0
        reasons.append("Optimized for printable wall art & poster designs")
    elif "clip art" in path_lower or "clipart" in path_lower:
        score += 45.0
        reasons.append("Matches digital clip art & graphics structure")
    elif "digital prints" in path_lower or "prints" in path_lower:
        score += 25.0
        reasons.append("Supports printable digital files")
    elif "drawing & illustration > digital" in path_lower:
        score += 25.0
        reasons.append("Supports digital illustration and artwork")
    elif "graphic design" in path_lower or "graphics" in path_lower:
        score += 25.0
        reasons.append("Supports graphic design assets")

    # 3. Properties and Allowed Values Evaluation
    craft_prop = next(
        (p for p in taxonomy_properties if "craft" in p.name.lower() or p.property_id == 82731),
        None,
    )

    if craft_prop:
        val_names = [v.get("name", "").lower() for v in craft_prop.possible_values if isinstance(v, dict)]

        has_sublimation_values = any(
            any(sub_val in v for sub_val in SUBLIMATION_PRINTING_CRAFT_VALUES)
            for v in val_names
        )

        all_paper_values = (
            len(val_names) > 0
            and all(
                any(paper_val in v for paper_val in PAPER_ONLY_CRAFT_VALUES)
                for v in val_names
            )
            and not has_sublimation_values
        )

        if craft_prop.is_required:
            if is_scrapbooking_paper and (all_paper_values or any("scrapbooking" in v for v in val_names)):
                score += 35.0
                reasons.append("Required Craft type directly supports scrapbooking and papercraft")
            elif is_sublimation_apparel and all_paper_values:
                # Severe mismatch: Required Craft type is paper-only for a sublimation/apparel product
                score -= 45.0
                has_mismatched_required = True
                mismatched_reason = (
                    "Craft type is required, but Etsy only offers paper/collage-related values "
                    f"({', '.join(v.get('name', '') for v in craft_prop.possible_values[:3])}) for this category."
                )
                warnings.append(
                    "Required Craft type values are limited to paper/collage uses and do not match apparel/sublimation intent."
                )
            elif is_sublimation_apparel and has_sublimation_values:
                score += 35.0
                reasons.append("Exposes sublimation and printing craft types")
            elif has_sublimation_values:
                score += 20.0
                reasons.append("Supports versatile printing and craft types")
        else:
            # Optional craft type
            if is_sublimation_apparel and has_sublimation_values:
                score += 20.0
                reasons.append("Offers optional sublimation and printing craft types")

    # 4. Check for physical dimensional requirements (negative on digital)
    physical_dim_props = [
        p for p in taxonomy_properties
        if p.is_required and any(dim in p.name.lower() for dim in ("length", "width", "height", "depth", "diameter", "weight"))
    ]
    if physical_dim_props:
        score -= 25.0
        warnings.append(
            f"Category requires physical dimensions ({', '.join(p.name for p in physical_dim_props)})"
        )

    # 5. Check for favorable digital graphic attributes
    useful_props = [
        p for p in taxonomy_properties
        if any(attr in p.name.lower() for attr in ("primary color", "secondary color", "holiday", "occasion", "style", "subject"))
    ]
    if useful_props:
        score += 10.0
        reasons.append("Supports visual metadata attributes (colors, holidays, styles)")

    # 6. Normalize score to 0.0 - 1.0
    normalized_score = min(max(round(score / 100.0, 2), 0.05), 1.0)

    # If there is a required attribute mismatch, cap score at 0.45 max
    if has_mismatched_required:
        normalized_score = min(normalized_score, 0.45)

    return TaxonomyFitResult(
        score=normalized_score,
        reasons=reasons,
        warnings=warnings,
        has_mismatched_required_attributes=has_mismatched_required,
        mismatched_required_reason=mismatched_reason,
    )
