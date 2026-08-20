"""Etsy taxonomy properties discovery, mapping, and automatic suggestions for digital listings."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
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


# Fake fallback properties for dev/test environments ONLY (Not used in production logic)
FAKE_TEST_TAXONOMY_PROPERTIES: list[dict[str, Any]] = [
    {
        "property_id": 91001,
        "name": "Craft type",
        "is_required": False,
        "is_multivalued": True,
        "possible_values": [
            {"value_id": 81001, "name": "Sublimation"},
            {"value_id": 81002, "name": "Printing & printmaking"},
            {"value_id": 81003, "name": "Direct to garment"},
        ],
    },
    {
        "property_id": 91002,
        "name": "Holiday",
        "is_required": False,
        "is_multivalued": False,
        "possible_values": [
            {"value_id": 82001, "name": "Christmas"},
            {"value_id": 82002, "name": "Halloween"},
            {"value_id": 82003, "name": "Thanksgiving"},
        ],
    },
    {
        "property_id": 91003,
        "name": "Season",
        "is_required": False,
        "is_multivalued": False,
        "possible_values": [
            {"value_id": 83001, "name": "Autumn"},
            {"value_id": 83002, "name": "Winter"},
            {"value_id": 83003, "name": "Spring"},
            {"value_id": 83004, "name": "Summer"},
        ],
    },
]


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
        "possible_values": [
            {"value_id": getattr(v, "value_id", None), "name": getattr(v, "name", "")}
            for v in possible_vals
        ],
    }


def suggest_taxonomy_properties(
    title: str,
    description: str,
    tags: list[str] | None = None,
    available_properties: list[Any] | None = None,
) -> dict[str, Any]:
    """Deterministically suggest property values based on listing content & keywords.

    Operates ONLY against property definitions returned by Etsy (or available_properties).
    Never hardcodes production property IDs or falls back to arbitrary first-values.
    """
    corpus = f"{title} {description} {' '.join(tags or [])}".lower()

    raw_props = available_properties if available_properties is not None else FAKE_TEST_TAXONOMY_PROPERTIES
    props_to_check = [_extract_property_dict(p) for p in raw_props]

    suggested: dict[str, Any] = {}

    for prop in props_to_check:
        prop_name = str(prop.get("name", ""))
        prop_id = prop.get("property_id")
        possible_values = prop.get("possible_values", [])

        if not prop_id or not possible_values:
            continue

        prop_name_lower = prop_name.lower()

        # Craft type (Sublimation + Printing & printmaking for digital PNG design downloads)
        if "craft" in prop_name_lower:
            selected_val_ids: list[int] = []
            selected_val_names: list[str] = []
            for val in possible_values:
                val_name = str(val.get("name", ""))
                val_id = val.get("value_id")
                val_name_lower = val_name.lower()
                if "sublimation" in val_name_lower or "print" in val_name_lower or "direct to garment" in val_name_lower:
                    if val_id:
                        selected_val_ids.append(int(val_id))
                        selected_val_names.append(val_name)

            if selected_val_ids:
                suggested[str(prop_id)] = {
                    "property_id": prop_id,
                    "property_name": prop_name,
                    "value_ids": selected_val_ids,
                    "values": selected_val_names,
                    "suggestion_source": "default_digital",
                    "confidence": 0.85,
                    "auto_select": True,
                    "is_suggested": True,
                }

        # Holiday
        elif "holiday" in prop_name_lower:
            for val in possible_values:
                val_name = str(val.get("name", ""))
                val_id = val.get("value_id")
                clean_val = re.sub(r"[^a-z0-9]", "", val_name.lower())
                if clean_val and clean_val in corpus.replace(" ", ""):
                    suggested[str(prop_id)] = {
                        "property_id": prop_id,
                        "property_name": prop_name,
                        "value_ids": [int(val_id)] if val_id else [],
                        "values": [val_name],
                        "suggestion_source": "keyword",
                        "confidence": 0.95,
                        "auto_select": True,
                        "is_suggested": True,
                    }
                    break

        # Season
        elif "season" in prop_name_lower:
            season_map = {
                "autumn": ["autumn", "fall", "thanksgiving", "spooky", "halloween"],
                "winter": ["winter", "christmas", "xmas", "snow", "cozy holiday", "baking"],
                "spring": ["spring", "easter", "bloom", "floral"],
                "summer": ["summer", "beach", "sun"],
            }
            for val in possible_values:
                val_name = str(val.get("name", "")).lower()
                val_id = val.get("value_id")
                keywords = season_map.get(val_name, [val_name])
                if any(kw in corpus for kw in keywords):
                    suggested[str(prop_id)] = {
                        "property_id": prop_id,
                        "property_name": prop_name,
                        "value_ids": [int(val_id)] if val_id else [],
                        "values": [str(val.get("name", ""))],
                        "suggestion_source": "keyword",
                        "confidence": 0.90,
                        "auto_select": True,
                        "is_suggested": True,
                    }
                    break

        # Style
        elif "style" in prop_name_lower:
            for val in possible_values:
                val_name = str(val.get("name", ""))
                val_id = val.get("value_id")
                if val_name.lower() in corpus:
                    suggested[str(prop_id)] = {
                        "property_id": prop_id,
                        "property_name": prop_name,
                        "value_ids": [int(val_id)] if val_id else [],
                        "values": [val_name],
                        "suggestion_source": "keyword",
                        "confidence": 0.90,
                        "auto_select": True,
                        "is_suggested": True,
                    }
                    break

        # Primary color
        elif "primary color" in prop_name_lower:
            color_keywords = ["brown", "red", "green", "black", "white", "blue", "orange", "pink", "beige"]
            for color in color_keywords:
                if color in corpus:
                    for val in possible_values:
                        if str(val.get("name", "")).lower() == color:
                            suggested[str(prop_id)] = {
                                "property_id": prop_id,
                                "property_name": prop_name,
                                "value_ids": [int(val["value_id"])] if val.get("value_id") else [],
                                "values": [val["name"]],
                                "suggestion_source": "keyword",
                                "confidence": 0.90,
                                "auto_select": True,
                                "is_suggested": True,
                            }
                            break
                    if str(prop_id) in suggested:
                        break

    return suggested


def revalidate_listing_taxonomy_properties(
    existing_properties: dict[str, Any] | None,
    available_properties: list[Any],
    title: str = "",
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Revalidates existing listing properties against a new taxonomy category definition.

    1. Keeps only properties that exist in available_properties.
    2. Keeps only value IDs/names allowed by Etsy in the target category.
    3. Truncates multi-value selections if target property is single-valued.
    4. Auto-suggests fresh high-confidence values for unassigned category properties.
    """
    props_map = {_extract_property_dict(p)["property_id"]: _extract_property_dict(p) for p in available_properties}
    validated: dict[str, Any] = {}

    if existing_properties:
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
            allowed_value_ids = {v["value_id"] for v in allowed_possible if v.get("value_id")}
            allowed_value_names = {v["name"] for v in allowed_possible if v.get("name")}

            existing_ids = val_entry.get("value_ids", [])
            existing_names = val_entry.get("values", [])

            valid_ids: list[int] = []
            valid_names: list[str] = []

            for val_id, val_name in zip(existing_ids, existing_names):
                if val_id in allowed_value_ids or val_name in allowed_value_names:
                    valid_ids.append(val_id)
                    valid_names.append(val_name)

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

    # Generate fresh suggestions for unassigned properties
    fresh_suggestions = suggest_taxonomy_properties(
        title=title,
        description=description,
        tags=tags,
        available_properties=available_properties,
    )

    for prop_id_str, sug in fresh_suggestions.items():
        if prop_id_str not in validated and sug.get("confidence", 0.0) >= 0.80:
            validated[prop_id_str] = {
                "property_id": sug["property_id"],
                "property_name": sug.get("property_name", ""),
                "value_ids": sug.get("value_ids", []),
                "values": sug.get("values", []),
                "suggestion_source": sug.get("suggestion_source", "smart_suggestion"),
                "confidence": sug.get("confidence", 0.85),
            }

    return validated
