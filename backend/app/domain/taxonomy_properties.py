"""Etsy taxonomy properties discovery, mapping, and validation for digital listings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TaxonomyPropertyValue:
    value_id: int
    name: str


@dataclass(frozen=True, slots=True)
class TaxonomyPropertyScale:
    scale_id: int
    display_name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class TaxonomyPropertyDefinition:
    property_id: int
    name: str
    display_name: str | None = None
    is_required: bool = False
    supports_attributes: bool = False
    supports_variations: bool = False
    is_multivalued: bool = False
    max_values_allowed: int | None = None
    scales: tuple[TaxonomyPropertyScale, ...] = ()
    possible_values: tuple[TaxonomyPropertyValue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "name": self.name,
            "display_name": self.display_name or self.name,
            "is_required": self.is_required,
            "supports_attributes": self.supports_attributes,
            "supports_variations": self.supports_variations,
            "is_multivalued": self.is_multivalued,
            "max_values_allowed": self.max_values_allowed,
            "scales": [
                {
                    "scale_id": s.scale_id,
                    "display_name": s.display_name,
                    "description": s.description,
                }
                for s in self.scales
            ],
            "possible_values": [
                {"value_id": v.value_id, "name": v.name} for v in self.possible_values
            ],
        }


def is_listing_attribute_property(prop: Any) -> bool:
    """Returns True if the property is a valid, eligible Etsy listing attribute.

    Rules based on official Etsy Open API v3:
    1. Primary rule: supports_attributes must be True.
    2. Properties with supports_attributes == False (e.g. variation-only properties
       where supports_variations == True) are NEVER listing attributes.
    3. Merely having possible_values does not make a property an attribute.
    """
    if isinstance(prop, dict):
        if "supports_attributes" in prop:
            return bool(prop["supports_attributes"])
        return bool(prop.get("is_required", False))
    if hasattr(prop, "supports_attributes"):
        return bool(prop.supports_attributes)
    return bool(getattr(prop, "is_required", False))


def filter_listing_attribute_properties(properties: list[Any]) -> list[Any]:
    """Filter raw taxonomy properties to only include eligible listing attributes."""
    return [p for p in properties if is_listing_attribute_property(p)]


def _extract_property_dict(prop: Any) -> dict[str, Any]:
    if isinstance(prop, dict):
        return prop
    if hasattr(prop, "to_dict"):
        return prop.to_dict()
    possible_vals = getattr(prop, "possible_values", ())
    scales = getattr(prop, "scales", ())
    return {
        "property_id": getattr(prop, "property_id", None),
        "name": getattr(prop, "name", ""),
        "display_name": getattr(prop, "display_name", None) or getattr(prop, "name", ""),
        "is_required": getattr(prop, "is_required", False),
        "is_multivalued": getattr(prop, "is_multivalued", False),
        "supports_attributes": getattr(prop, "supports_attributes", False),
        "supports_variations": getattr(prop, "supports_variations", False),
        "max_values_allowed": getattr(prop, "max_values_allowed", None),
        "scales": [
            {
                "scale_id": getattr(s, "scale_id", None)
                if not isinstance(s, dict)
                else s.get("scale_id"),
                "display_name": getattr(s, "display_name", "")
                if not isinstance(s, dict)
                else s.get("display_name", ""),
                "description": getattr(s, "description", "")
                if not isinstance(s, dict)
                else s.get("description", ""),
            }
            for s in scales
        ],
        "possible_values": [
            {
                "value_id": getattr(v, "value_id", None)
                if not isinstance(v, dict)
                else v.get("value_id"),
                "name": getattr(v, "name", "") if not isinstance(v, dict) else v.get("name", ""),
            }
            for v in possible_vals
        ],
    }


def revalidate_listing_taxonomy_properties(
    existing_properties: dict[str, Any] | None,
    available_properties: list[Any],
) -> dict[str, Any]:
    """Revalidates existing listing properties against a taxonomy category definition.

    1. Only considers attribute-eligible properties (supports_attributes == True).
    2. Removes stale property IDs that do not belong to the current taxonomy.
    3. Keeps only value IDs/names allowed by Etsy in the target category.
    4. Supports scale-based measurement properties (e.g. Width, Height).
    5. Respects single vs multi-value rules and max_values_allowed.
    6. NEVER auto-fills or invents any values. Unselected properties remain empty.
    """
    if not existing_properties:
        return {}

    # Only include attribute-eligible properties
    eligible_props = filter_listing_attribute_properties(available_properties)
    if not eligible_props and available_properties:
        # available_properties were provided but none were attribute-eligible
        return {}

    props_map = {
        _extract_property_dict(p)["property_id"]: _extract_property_dict(p)
        for p in eligible_props
        if _extract_property_dict(p).get("property_id") is not None
    }

    if not props_map:
        # Fallback if available_properties could not be loaded
        return existing_properties

    validated: dict[str, Any] = {}

    for prop_id_str, val_entry in existing_properties.items():
        if not isinstance(val_entry, dict):
            continue
        prop_id = val_entry.get("property_id")
        if not prop_id and prop_id_str.isdigit():
            prop_id = int(prop_id_str)

        if not prop_id or prop_id not in props_map:
            continue

        target_prop = props_map[prop_id]
        allowed_possible = target_prop.get("possible_values", [])
        allowed_scales = target_prop.get("scales", [])

        # Check if this is a scale-based property (e.g. Width, Height)
        if allowed_scales and not allowed_possible:
            scale_id = val_entry.get("scale_id")
            allowed_scale_ids = {
                s["scale_id"] for s in allowed_scales if s.get("scale_id") is not None
            }
            raw_val = val_entry.get("value") or (
                val_entry.get("values", [""])[0] if val_entry.get("values") else None
            )
            if scale_id in allowed_scale_ids and raw_val:
                matched_scale = next(
                    (s for s in allowed_scales if s.get("scale_id") == scale_id), None
                )
                validated[str(prop_id)] = {
                    "property_id": prop_id,
                    "property_name": target_prop.get("display_name") or target_prop.get("name", ""),
                    "scale_id": scale_id,
                    "scale_name": matched_scale.get("display_name", "") if matched_scale else "",
                    "value": str(raw_val).strip(),
                    "values": [str(raw_val).strip()],
                    "value_ids": [],
                }
            continue

        allowed_value_ids = {
            v["value_id"] for v in allowed_possible if v.get("value_id") is not None
        }
        allowed_value_names = {v["name"] for v in allowed_possible if v.get("name")}

        existing_ids = val_entry.get("value_ids", [])
        existing_names = val_entry.get("values", [])

        valid_ids: list[int] = []
        valid_names: list[str] = []

        # If both IDs and names provided
        if existing_ids and existing_names and len(existing_ids) == len(existing_names):
            for vid, vname in zip(existing_ids, existing_names):
                if vid in allowed_value_ids or vname in allowed_value_names:
                    matched = next(
                        (
                            v
                            for v in allowed_possible
                            if v.get("value_id") == vid or v.get("name") == vname
                        ),
                        None,
                    )
                    if matched:
                        valid_ids.append(matched["value_id"])
                        valid_names.append(matched["name"])
        elif existing_ids:
            for vid in existing_ids:
                matched = next((v for v in allowed_possible if v.get("value_id") == vid), None)
                if matched:
                    valid_ids.append(matched["value_id"])
                    valid_names.append(matched["name"])
        elif existing_names:
            for vname in existing_names:
                matched = next((v for v in allowed_possible if v.get("name") == vname), None)
                if matched:
                    valid_ids.append(matched["value_id"])
                    valid_names.append(matched["name"])

        if not target_prop.get("is_multivalued", False):
            valid_ids = valid_ids[:1]
            valid_names = valid_names[:1]
        elif target_prop.get("max_values_allowed"):
            max_allowed = int(target_prop["max_values_allowed"])
            valid_ids = valid_ids[:max_allowed]
            valid_names = valid_names[:max_allowed]

        if valid_ids or valid_names:
            validated[str(prop_id)] = {
                "property_id": prop_id,
                "property_name": target_prop.get("display_name") or target_prop.get("name", ""),
                "value_ids": valid_ids,
                "values": valid_names,
            }

    return validated


def check_required_taxonomy_properties(
    saved_properties: dict[str, Any] | None,
    available_properties: list[Any],
) -> list[str]:
    """Returns a list of property names for required Etsy properties that have no selection."""
    missing: list[str] = []
    saved = saved_properties or {}

    eligible_props = filter_listing_attribute_properties(available_properties)
    for p in eligible_props:
        prop = _extract_property_dict(p)
        if prop.get("is_required"):
            p_id_str = str(prop.get("property_id"))
            entry = saved.get(p_id_str)
            if not entry or not entry.get("values") or len(entry.get("values", [])) == 0:
                missing.append(prop.get("display_name") or prop.get("name", f"Property {p_id_str}"))

    return missing
