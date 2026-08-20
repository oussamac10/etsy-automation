"""Etsy taxonomy properties discovery, mapping, and validation for digital listings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TaxonomyPropertyValue:
    value_id: int
    name: str


@dataclass(frozen=True, slots=True)
class TaxonomyPropertyDefinition:
    property_id: int
    name: str
    is_required: bool
    supports_attributes: bool
    is_multivalued: bool
    possible_values: tuple[TaxonomyPropertyValue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "name": self.name,
            "is_required": self.is_required,
            "supports_attributes": self.supports_attributes,
            "is_multivalued": self.is_multivalued,
            "possible_values": [
                {"value_id": v.value_id, "name": v.name} for v in self.possible_values
            ],
        }


def _extract_property_dict(prop: Any) -> dict[str, Any]:
    if isinstance(prop, dict):
        return prop
    if hasattr(prop, "to_dict"):
        return prop.to_dict()
    possible_vals = getattr(prop, "possible_values", ())
    return {
        "property_id": getattr(prop, "property_id", None),
        "name": getattr(prop, "name", ""),
        "is_required": getattr(prop, "is_required", False),
        "is_multivalued": getattr(prop, "is_multivalued", False),
        "supports_attributes": getattr(prop, "supports_attributes", False),
        "possible_values": [
            {"value_id": getattr(v, "value_id", None), "name": getattr(v, "name", "")}
            for v in possible_vals
        ],
    }


def revalidate_listing_taxonomy_properties(
    existing_properties: dict[str, Any] | None,
    available_properties: list[Any],
) -> dict[str, Any]:
    """Revalidates existing listing properties against a new taxonomy category definition.

    1. Keeps only properties that exist in available_properties.
    2. Keeps only value IDs/names allowed by Etsy in the target category.
    3. Truncates multi-value selections if target property is single-valued.
    4. NEVER auto-fills or invents any values. Unselected properties remain empty.
    """
    props_map = {
        _extract_property_dict(p)["property_id"]: _extract_property_dict(p)
        for p in available_properties
        if _extract_property_dict(p).get("property_id") is not None
    }
    validated: dict[str, Any] = {}

    if not existing_properties:
        return validated

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
        allowed_value_ids = {
            v["value_id"] for v in allowed_possible if v.get("value_id") is not None
        }
        allowed_value_names = {
            v["name"] for v in allowed_possible if v.get("name")
        }

        existing_ids = val_entry.get("value_ids", [])
        existing_names = val_entry.get("values", [])

        valid_ids: list[int] = []
        valid_names: list[str] = []

        # If both IDs and names provided
        if existing_ids and existing_names and len(existing_ids) == len(existing_names):
            for vid, vname in zip(existing_ids, existing_names):
                if vid in allowed_value_ids or vname in allowed_value_names:
                    # Match canonical name from target if possible
                    matched = next((v for v in allowed_possible if v.get("value_id") == vid or v.get("name") == vname), None)
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

        if valid_ids or valid_names:
            validated[str(prop_id)] = {
                "property_id": prop_id,
                "property_name": target_prop.get("name", ""),
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

    for p in available_properties:
        prop = _extract_property_dict(p)
        if prop.get("is_required"):
            p_id_str = str(prop.get("property_id"))
            entry = saved.get(p_id_str)
            if not entry or not entry.get("values") or len(entry.get("values", [])) == 0:
                missing.append(prop.get("name", f"Property {p_id_str}"))

    return missing
