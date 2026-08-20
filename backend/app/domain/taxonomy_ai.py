"""Domain logic, context assembly, prompt engineering, and strict validation for AI taxonomy attribute suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator


@dataclass(frozen=True, slots=True)
class ValidatedTaxonomySuggestion:
    """A validated attribute suggestion strictly matching an Etsy taxonomy property."""

    property_id: int
    property_name: str
    value_ids: list[int]
    values: list[str]
    confidence: float
    reason: str
    is_required: bool
    is_multivalued: bool
    is_high_confidence: bool  # confidence >= 0.85

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "property_name": self.property_name,
            "value_ids": self.value_ids,
            "values": self.values,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
            "is_required": self.is_required,
            "is_multivalued": self.is_multivalued,
            "is_high_confidence": self.is_high_confidence,
        }


class RawAiSelectionItem(BaseModel):
    """Raw single selection item from LLM JSON response."""

    property_id: int
    value_ids: list[int] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=500)


class RawAiTaxonomyResponse(BaseModel):
    """Raw structured output schema requested from LLM."""

    selections: list[RawAiSelectionItem] = Field(default_factory=list)


def compute_taxonomy_content_fingerprint(
    workflow_id: str,
    taxonomy_id: int,
    title: str,
    description: str,
    tags: list[str],
    properties: list[Any],
    concept_title: str | None = None,
    slogan: str | None = None,
    seasonality: str | None = None,
) -> str:
    """Compute a deterministic hash fingerprint representing all input factors."""
    prop_repr: list[tuple[int, list[int]]] = []
    for p in properties:
        p_id = getattr(p, "property_id", None) or (p.get("property_id") if isinstance(p, dict) else None)
        raw_vals = getattr(p, "possible_values", []) or (p.get("possible_values", []) if isinstance(p, dict) else [])
        val_ids: list[int] = []
        for v in raw_vals:
            v_id = getattr(v, "value_id", None) or (v.get("value_id") if isinstance(v, dict) else None)
            if v_id is not None:
                val_ids.append(int(v_id))
        if p_id is not None:
            prop_repr.append((int(p_id), sorted(val_ids)))

    payload = {
        "wf": str(workflow_id),
        "tax": int(taxonomy_id),
        "title": title.strip().lower(),
        "desc": description.strip()[:200].lower(),
        "tags": sorted([t.strip().lower() for t in tags]),
        "props": sorted(prop_repr, key=lambda x: x[0]),
        "concept": (concept_title or "").strip().lower(),
        "slogan": (slogan or "").strip().lower(),
        "season": (seasonality or "").strip().lower(),
    }
    dumped = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


def build_taxonomy_ai_context(
    workflow_id: str,
    workflow_name: str,
    concept_title: str | None,
    concept_description: str | None,
    slogan: str | None,
    seasonality: str | None,
    target_buyer: str | None,
    intended_product_uses: list[str] | None,
    title: str,
    description: str,
    tags: list[str],
    taxonomy_id: int,
    taxonomy_path: str | None,
    available_properties: list[Any],
    artwork_colors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble a compact, structured campaign context dictionary for the LLM."""
    props_list: list[dict[str, Any]] = []
    for p in available_properties:
        p_id = getattr(p, "property_id", None) or (p.get("property_id") if isinstance(p, dict) else None)
        p_name = getattr(p, "name", None) or (p.get("name") if isinstance(p, dict) else "")
        p_req = getattr(p, "is_required", False) or (p.get("is_required", False) if isinstance(p, dict) else False)
        p_multi = getattr(p, "is_multivalued", False) or (p.get("is_multivalued", False) if isinstance(p, dict) else False)
        raw_vals = getattr(p, "possible_values", []) or (p.get("possible_values", []) if isinstance(p, dict) else [])

        vals_list: list[dict[str, Any]] = []
        for v in raw_vals:
            v_id = getattr(v, "value_id", None) or (v.get("value_id") if isinstance(v, dict) else None)
            v_name = getattr(v, "name", None) or (v.get("name") if isinstance(v, dict) else "")
            if v_id is not None and v_name:
                vals_list.append({"value_id": int(v_id), "name": str(v_name)})

        if p_id is not None and p_name and vals_list:
            props_list.append({
                "property_id": int(p_id),
                "name": str(p_name),
                "is_required": bool(p_req),
                "is_multivalued": bool(p_multi),
                "possible_values": vals_list,
            })

    return {
        "campaign": {
            "workflow_id": str(workflow_id),
            "campaign_name": workflow_name,
            "concept_title": concept_title or workflow_name,
            "concept_description": concept_description or "",
            "slogan": slogan or "",
            "seasonality": seasonality or "evergreen",
            "target_buyer": target_buyer or "Crafters, POD buyers, apparel creators",
            "intended_product_uses": intended_product_uses or ["sublimation", "t-shirt", "mug", "transparent png"],
            "artwork_colors": artwork_colors or [],
        },
        "listing": {
            "title": title,
            "description": description[:600],
            "tags": tags,
        },
        "taxonomy": {
            "taxonomy_id": int(taxonomy_id),
            "taxonomy_path": taxonomy_path or "Digital Artwork & Clip Art",
        },
        "allowed_properties": props_list,
    }


def build_taxonomy_ai_prompt(context: dict[str, Any]) -> str:
    """Construct a strict JSON prompt instructing the LLM to select from allowed Etsy properties."""
    context_json = json.dumps(context, indent=2)

    return f"""You are selecting Etsy listing category attributes from a fixed, authoritative set supplied by the Etsy marketplace API.

CAMPAIGN & ETSY PROPERTY CONTEXT:
{context_json}

CRITICAL RULES:
1. ONLY select from the provided property_id and value_id values in "allowed_properties".
2. DO NOT invent new property IDs or value IDs under any circumstances.
3. DO NOT select an attribute value unless the campaign concept, title, tags, seasonality, or intended uses explicitly support it.
4. For single-valued properties (is_multivalued = false), provide at most ONE value_id in the value_ids list.
5. For multivalued properties (is_multivalued = true), you may select 1 to 3 relevant value_ids if clearly supported.
6. If an optional property is not relevant to this design, DO NOT include it in your selections.
7. Assign realistic confidence scores:
   - >= 0.85 (High confidence): Explicitly mentioned in title, tags, or core concept (e.g. Christmas for holiday, Sublimation for craft type).
   - 0.65 - 0.84 (Medium confidence): Strongly implied by theme or seasonality.
   - < 0.65: Low confidence or uncertain (avoid selecting unless required).
8. Provide a concise 1-sentence reason for each selection explaining why it matches this specific campaign.

OUTPUT STRICT JSON ONLY MATCHING THIS SCHEMA:
{{
  "selections": [
    {{
      "property_id": 82731,
      "value_ids": [441908],
      "confidence": 0.95,
      "reason": "The campaign explicitly targets sublimation t-shirts and mug printing."
    }}
  ]
}}
"""


def validate_ai_taxonomy_suggestions(
    raw_response: dict[str, Any] | RawAiTaxonomyResponse,
    available_properties: list[Any],
) -> list[ValidatedTaxonomySuggestion]:
    """Strictly validate AI selections against authoritative Etsy taxonomy properties.

    - Rejects any property_id not in available_properties.
    - Rejects any value_id not in that property's possible_values.
    - Enforces single vs multivalued constraints.
    - Removes duplicate values.
    - Clamps confidence scores to [0.0, 1.0].
    - Reconstructs property names and value names directly from Etsy definitions.
    """
    prop_lookup: dict[int, dict[str, Any]] = {}
    for p in available_properties:
        p_id = getattr(p, "property_id", None) or (p.get("property_id") if isinstance(p, dict) else None)
        p_name = getattr(p, "name", None) or (p.get("name") if isinstance(p, dict) else "")
        p_req = getattr(p, "is_required", False) or (p.get("is_required", False) if isinstance(p, dict) else False)
        p_multi = getattr(p, "is_multivalued", False) or (p.get("is_multivalued", False) if isinstance(p, dict) else False)
        raw_vals = getattr(p, "possible_values", []) or (p.get("possible_values", []) if isinstance(p, dict) else [])

        val_map: dict[int, str] = {}
        for v in raw_vals:
            v_id = getattr(v, "value_id", None) or (v.get("value_id") if isinstance(v, dict) else None)
            v_name = getattr(v, "name", None) or (v.get("name") if isinstance(v, dict) else "")
            if v_id is not None and v_name:
                val_map[int(v_id)] = str(v_name)

        if p_id is not None:
            prop_lookup[int(p_id)] = {
                "name": str(p_name),
                "is_required": bool(p_req),
                "is_multivalued": bool(p_multi),
                "values": val_map,
            }

    raw_selections: list[dict[str, Any]] = []
    if isinstance(raw_response, RawAiTaxonomyResponse):
        raw_selections = [s.model_dump() for s in raw_response.selections]
    elif isinstance(raw_response, dict):
        raw_selections = raw_response.get("selections", [])

    validated: list[ValidatedTaxonomySuggestion] = []
    seen_props: set[int] = set()

    for item in raw_selections:
        if not isinstance(item, dict):
            continue

        raw_prop_id = item.get("property_id")
        if raw_prop_id is None:
            continue

        try:
            prop_id = int(raw_prop_id)
        except (ValueError, TypeError):
            continue

        # Drop unknown properties
        if prop_id not in prop_lookup or prop_id in seen_props:
            continue

        prop_info = prop_lookup[prop_id]
        val_map = prop_info["values"]
        is_multi = prop_info["is_multivalued"]
        is_req = prop_info["is_required"]
        prop_name = prop_info["name"]

        # Validate value IDs
        raw_val_ids = item.get("value_ids", [])
        if not isinstance(raw_val_ids, list):
            raw_val_ids = [raw_val_ids] if raw_val_ids is not None else []

        valid_val_ids: list[int] = []
        valid_val_names: list[str] = []

        for rv in raw_val_ids:
            try:
                vid = int(rv)
            except (ValueError, TypeError):
                continue
            if vid in val_map and vid not in valid_val_ids:
                valid_val_ids.append(vid)
                valid_val_names.append(val_map[vid])

        # For single-valued properties, keep only the first valid value
        if not is_multi and len(valid_val_ids) > 1:
            valid_val_ids = valid_val_ids[:1]
            valid_val_names = valid_val_names[:1]

        # If no valid values survived, drop this suggestion
        if not valid_val_ids:
            continue

        # Clamp confidence
        raw_conf = item.get("confidence", 0.8)
        try:
            confidence = max(0.0, min(1.0, float(raw_conf)))
        except (ValueError, TypeError):
            confidence = 0.8

        reason = str(item.get("reason", "")).strip()
        if not reason:
            reason = f"Matches campaign {prop_name.lower()} attributes."

        seen_props.add(prop_id)
        validated.append(
            ValidatedTaxonomySuggestion(
                property_id=prop_id,
                property_name=prop_name,
                value_ids=valid_val_ids,
                values=valid_val_names,
                confidence=confidence,
                reason=reason,
                is_required=is_req,
                is_multivalued=is_multi,
                is_high_confidence=confidence >= 0.85,
            )
        )

    # Sort: required first, then high confidence, then descending confidence
    validated.sort(
        key=lambda s: (
            0 if s.is_required else 1,
            0 if s.is_high_confidence else 1,
            -s.confidence,
        )
    )

    return validated
