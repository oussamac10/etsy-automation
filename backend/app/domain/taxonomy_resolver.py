"""Deterministic Etsy Seller Taxonomy Category Resolver.

Resolves the most appropriate official Etsy seller taxonomy category for digital
transparent PNG graphics, clip art, sublimation designs, and digital prints.
Strictly relies on real Etsy taxonomy nodes and property definitions.
Evaluates attribute compatibility to avoid paper-only categories for apparel/sublimation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Coroutine, Mapping, Sequence

from app.domain.taxonomy_fitness import (
    TaxonomyFitResult,
    evaluate_taxonomy_fit,
    is_physical_disqualified,
)
from app.ports.providers import EtsyTaxonomyNode, EtsyTaxonomyProperty


@dataclass(frozen=True, slots=True)
class TaxonomyResolution:
    taxonomy_id: int
    taxonomy_path: str
    confidence: float
    is_fallback: bool = False
    fit_result: TaxonomyFitResult | None = None


class EtsyTaxonomyResolver:
    """Taxonomy category resolver evaluating both path and Etsy property compatibility."""

    # Curated prioritized digital category IDs on Etsy
    CLIP_ART_ID = 6844  # Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files
    DIGITAL_DRAWING_ID = 77  # Art & Collectibles > Drawing & Illustration > Digital
    DIGITAL_PRINTS_ID = 2078  # Art & Collectibles > Prints > Digital Prints
    GRAPHIC_DESIGN_ID = 769  # Paper & Party Supplies > ... > Graphic Design > Store Graphics

    def __init__(self) -> None:
        self._properties_cache: dict[int, list[EtsyTaxonomyProperty]] = {}

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
        return is_physical_disqualified(path)

    def resolve(
        self,
        *,
        title: str,
        description: str | None = None,
        tags: Sequence[str] | None = None,
        product_type: str | None = None,
        intended_product_uses: Sequence[str] | None = None,
        slogan: str | None = None,
        concept: str | None = None,
        nodes: Sequence[EtsyTaxonomyNode] | None = None,
        properties_map: Mapping[int, Sequence[EtsyTaxonomyProperty]] | None = None,
    ) -> TaxonomyResolution:
        """Deterministically resolve the optimal digital Etsy taxonomy category.

        Inspects candidate nodes and evaluated property fitness when available.
        """
        campaign_context = {
            "title": title,
            "description": description or "",
            "tags": list(tags or []),
            "product_type": product_type or "",
            "intended_product_uses": list(intended_product_uses or []),
            "slogan": slogan or "",
            "concept": concept or "",
        }

        # 1. If nodes are provided, evaluate them with property fitness
        if nodes:
            flat_nodes = self.flatten_nodes(nodes)
            leaf_nodes = [n for n in flat_nodes if not n.children]
            candidate_pool = leaf_nodes if leaf_nodes else flat_nodes

            valid_candidates = [
                n for n in candidate_pool if not self.is_physical_disqualified(n.full_path)
            ]

            scored_candidates: list[tuple[float, EtsyTaxonomyNode, TaxonomyFitResult]] = []

            for node in valid_candidates:
                node_props = (properties_map or {}).get(node.id, [])
                fit = evaluate_taxonomy_fit(
                    taxonomy_node=node,
                    taxonomy_properties=node_props,
                    campaign_context=campaign_context,
                )

                if fit.score > 0:
                    scored_candidates.append((fit.score, node, fit))

            if scored_candidates:
                scored_candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_node, best_fit = scored_candidates[0]
                if best_fit.has_mismatched_required_attributes:
                    warnings = list(best_fit.warnings)
                    if not any("precisely matches" in w for w in warnings):
                        warnings.append("Etsy does not currently expose a Craft type that precisely matches this product's intended use.")
                    best_fit = TaxonomyFitResult(
                        score=best_fit.score,
                        fit=best_fit.fit,
                        blocking_mismatch=best_fit.blocking_mismatch,
                        reasons=best_fit.reasons,
                        warnings=warnings,
                        has_mismatched_required_attributes=best_fit.has_mismatched_required_attributes,
                        mismatched_required_reason=best_fit.mismatched_required_reason,
                        best_available=True,
                        campaign_intent=best_fit.campaign_intent,
                    )
                return TaxonomyResolution(
                    taxonomy_id=best_node.id,
                    taxonomy_path=best_node.full_path,
                    confidence=best_score,
                    is_fallback=False,
                    fit_result=best_fit,
                )

        # 2. Curated standard fallback if nodes tree was not passed or contained no matches
        combined_text = f"{title} {' '.join(tags or [])} {product_type or ''} {' '.join(intended_product_uses or [])}".lower()
        tokens = set(re.findall(r"\b[a-z0-9_-]+\b", combined_text))

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

        # Default for transparent PNG artwork designs
        return TaxonomyResolution(
            taxonomy_id=self.CLIP_ART_ID,
            taxonomy_path="Craft Supplies & Tools > Canvas & Surfaces > Stencils, Templates & Transfers > Clip Art & Image Files",
            confidence=0.95,
            is_fallback=True,
        )

    async def resolve_with_gateway(
        self,
        *,
        title: str,
        description: str | None = None,
        tags: Sequence[str] | None = None,
        product_type: str | None = None,
        intended_product_uses: Sequence[str] | None = None,
        slogan: str | None = None,
        concept: str | None = None,
        nodes: Sequence[EtsyTaxonomyNode] | None = None,
        property_fetcher: (
            Callable[[int], Coroutine[Any, Any, list[EtsyTaxonomyProperty]]] | None
        ) = None,
    ) -> TaxonomyResolution:
        """Resolve category by dynamically fetching properties for top candidate nodes."""
        campaign_context = {
            "title": title,
            "description": description or "",
            "tags": list(tags or []),
            "product_type": product_type or "",
            "intended_product_uses": list(intended_product_uses or []),
            "slogan": slogan or "",
            "concept": concept or "",
        }

        if not nodes:
            return self.resolve(
                title=title,
                description=description,
                tags=tags,
                product_type=product_type,
                intended_product_uses=intended_product_uses,
                slogan=slogan,
                concept=concept,
            )

        flat_nodes = self.flatten_nodes(nodes)
        leaf_nodes = [n for n in flat_nodes if not n.children]
        candidate_pool = leaf_nodes if leaf_nodes else flat_nodes
        valid_candidates = [
            n for n in candidate_pool if not self.is_physical_disqualified(n.full_path)
        ]

        # Prioritize top candidates to avoid fetching properties for all nodes
        def pre_rank_heuristic(n: EtsyTaxonomyNode) -> int:
            p = n.full_path.lower()
            if "clip art" in p or "clipart" in p:
                return 40
            if "digital prints" in p:
                return 35
            if "drawing & illustration > digital" in p:
                return 35
            if "digital" in p or "graphics" in p:
                return 30
            if "craft supplies" in p:
                return 20
            return 10

        valid_candidates.sort(key=pre_rank_heuristic, reverse=True)
        top_candidates = valid_candidates[:10]

        properties_map: dict[int, list[EtsyTaxonomyProperty]] = {}
        for candidate in top_candidates:
            if candidate.id in self._properties_cache:
                properties_map[candidate.id] = self._properties_cache[candidate.id]
            elif property_fetcher is not None:
                try:
                    props = await property_fetcher(candidate.id)
                    self._properties_cache[candidate.id] = props
                    properties_map[candidate.id] = props
                except Exception:
                    properties_map[candidate.id] = []

        return self.resolve(
            title=title,
            description=description,
            tags=tags,
            product_type=product_type,
            intended_product_uses=intended_product_uses,
            slogan=slogan,
            concept=concept,
            nodes=top_candidates,
            properties_map=properties_map,
        )
