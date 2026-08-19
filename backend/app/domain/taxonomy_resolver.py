"""Deterministic Etsy Seller Taxonomy Category Resolver.

Resolves the most appropriate official Etsy seller taxonomy category for digital
transparent PNG graphics, clip art, sublimation designs, and digital prints.
Strictly disqualifies physical product categories (e.g. Plates, Mugs, Apparel).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from app.domain.errors import DomainError
from app.ports.providers import EtsyTaxonomyNode


@dataclass(frozen=True, slots=True)
class TaxonomyResolution:
    taxonomy_id: int
    taxonomy_path: str
    confidence: float
    is_fallback: bool = False


# Disqualified physical path tokens
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


class EtsyTaxonomyResolver:
    """Deterministic taxonomy category resolver for digital PNG POD products."""

    # Curated prioritized digital category IDs on Etsy
    CLIP_ART_ID = 6844  # Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files
    DIGITAL_DRAWING_ID = 77  # Art & Collectibles > Drawing & Illustration > Digital
    DIGITAL_PRINTS_ID = 2078  # Art & Collectibles > Prints > Digital Prints
    GRAPHIC_DESIGN_ID = 769  # Paper & Party Supplies > ... > Graphic Design > Store Graphics

    def flatten_nodes(self, nodes: Sequence[EtsyTaxonomyNode]) -> list[EtsyTaxonomyNode]:
        """Flatten hierarchical taxonomy tree into a flat list."""
        flat: list[EtsyTaxonomyNode] = []

        def traverse(node: EtsyTaxonomyNode) -> None:
            flat.append(node)
            for child in node.children:
                traverse(child)

        for n in nodes:
            traverse(n)
        return flat

    def is_physical_disqualified(self, path: str) -> bool:
        """Check if a taxonomy path clearly represents a physical product."""
        clean = path.lower()
        # If the path explicitly mentions digital/clip art, ensure it's not a physical parent like 'Home & Living'
        if clean.startswith("home & living") or clean.startswith("clothing") or clean.startswith("kitchen"):
            return True
        tokens = set(re.findall(r"\b[a-z-]+\b", clean))
        return bool(tokens & DISQUALIFIED_PHYSICAL_KEYWORDS)

    def resolve(
        self,
        *,
        title: str,
        tags: Sequence[str] | None = None,
        product_type: str | None = None,
        nodes: Sequence[EtsyTaxonomyNode] | None = None,
    ) -> TaxonomyResolution:
        """Deterministically resolve the optimal digital Etsy taxonomy category.

        Raises:
            DomainError: If nodes are empty or no valid digital category can be found.
        """
        combined_text = f"{title} {' '.join(tags or [])} {product_type or ''}".lower()
        tokens = set(re.findall(r"\b[a-z0-9_-]+\b", combined_text))

        # 1. If nodes are provided, evaluate them deterministically
        if nodes:
            flat_nodes = self.flatten_nodes(nodes)
            leaf_nodes = [n for n in flat_nodes if not n.children]
            candidate_pool = leaf_nodes if leaf_nodes else flat_nodes

            scored_candidates: list[tuple[float, EtsyTaxonomyNode]] = []

            for node in candidate_pool:
                path_lower = node.full_path.lower()
                name_lower = node.name.lower()

                # Disqualify physical paths
                if self.is_physical_disqualified(node.full_path):
                    continue

                score = 0.0

                # Base digital affinity
                if node.id == self.CLIP_ART_ID or "clip art" in path_lower:
                    score += 100.0
                elif node.id == self.DIGITAL_PRINTS_ID or "digital prints" in path_lower:
                    score += 85.0
                elif node.id == self.DIGITAL_DRAWING_ID or "drawing & illustration > digital" in path_lower:
                    score += 85.0
                elif "digital" in path_lower or "graphics" in path_lower:
                    score += 50.0
                else:
                    # Non-digital categories are heavily downweighted
                    score -= 50.0

                # Specific keyword boosts
                if any(k in tokens for k in ("clipart", "clip art", "png", "sublimation", "sticker", "design", "graphic")):
                    if "clip art" in path_lower or node.id == self.CLIP_ART_ID:
                        score += 30.0

                if any(k in tokens for k in ("poster", "print", "printable", "wall art", "decor")):
                    if "prints" in path_lower or node.id == self.DIGITAL_PRINTS_ID:
                        score += 30.0

                if any(k in tokens for k in ("illustration", "drawing", "portrait", "sketch")):
                    if "drawing" in path_lower or node.id == self.DIGITAL_DRAWING_ID:
                        score += 30.0

                if score > 0:
                    scored_candidates.append((score, node))

            if scored_candidates:
                scored_candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_node = scored_candidates[0]
                confidence = min(round(best_score / 120.0, 2), 1.0)
                return TaxonomyResolution(
                    taxonomy_id=best_node.id,
                    taxonomy_path=best_node.full_path,
                    confidence=confidence,
                    is_fallback=False,
                )

        # 2. Curated standard fallback if nodes tree was not passed or contained no matches
        # Determine between Clip Art, Digital Prints, and Digital Illustration
        if any(k in tokens for k in ("poster", "print", "printable", "wall art")):
            return TaxonomyResolution(
                taxonomy_id=self.DIGITAL_PRINTS_ID,
                taxonomy_path="Art & Collectibles > Prints > Digital Prints",
                confidence=0.9,
                is_fallback=True,
            )
        elif any(k in tokens for k in ("illustration", "drawing", "portrait")):
            return TaxonomyResolution(
                taxonomy_id=self.DIGITAL_DRAWING_ID,
                taxonomy_path="Art & Collectibles > Drawing & Illustration > Digital",
                confidence=0.9,
                is_fallback=True,
            )

        # Default for transparent PNG artwork designs (shirts, mugs, sublimation, stickers)
        return TaxonomyResolution(
            taxonomy_id=self.CLIP_ART_ID,
            taxonomy_path="Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
            confidence=0.95,
            is_fallback=True,
        )
