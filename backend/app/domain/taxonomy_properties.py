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


# Common standard properties available on Etsy for Clip Art / Digital Art categories
STANDARD_DIGITAL_PROPERTIES: list[dict[str, Any]] = [
    {
        "property_id": 513,
        "name": "Craft type",
        "is_required": False,
        "is_multivalued": True,
        "possible_values": [
            {"value_id": 1001, "name": "Sublimation"},
            {"value_id": 1002, "name": "Printing & printmaking"},
            {"value_id": 1003, "name": "Direct to garment"},
            {"value_id": 1004, "name": "Card making & stationery"},
            {"value_id": 1005, "name": "Scrapbooking"},
        ],
    },
    {
        "property_id": 514,
        "name": "Holiday",
        "is_required": False,
        "is_multivalued": False,
        "possible_values": [
            {"value_id": 2001, "name": "Christmas"},
            {"value_id": 2002, "name": "Halloween"},
            {"value_id": 2003, "name": "Thanksgiving"},
            {"value_id": 2004, "name": "Easter"},
            {"value_id": 2005, "name": "Valentine's Day"},
            {"value_id": 2006, "name": "Mother's Day"},
            {"value_id": 2007, "name": "Father's Day"},
            {"value_id": 2008, "name": "4th of July"},
        ],
    },
    {
        "property_id": 515,
        "name": "Season",
        "is_required": False,
        "is_multivalued": False,
        "possible_values": [
            {"value_id": 3001, "name": "Autumn"},
            {"value_id": 3002, "name": "Winter"},
            {"value_id": 3003, "name": "Spring"},
            {"value_id": 3004, "name": "Summer"},
        ],
    },
    {
        "property_id": 516,
        "name": "Primary color",
        "is_required": False,
        "is_multivalued": False,
        "possible_values": [
            {"value_id": 4001, "name": "Brown"},
            {"value_id": 4002, "name": "Red"},
            {"value_id": 4003, "name": "Green"},
            {"value_id": 4004, "name": "Black"},
            {"value_id": 4005, "name": "White"},
            {"value_id": 4006, "name": "Blue"},
            {"value_id": 4007, "name": "Orange"},
            {"value_id": 4008, "name": "Pink"},
            {"value_id": 4009, "name": "Beige"},
        ],
    },
    {
        "property_id": 517,
        "name": "Style",
        "is_required": False,
        "is_multivalued": False,
        "possible_values": [
            {"value_id": 5001, "name": "Cottagecore"},
            {"value_id": 5002, "name": "Retro"},
            {"value_id": 5003, "name": "Vintage"},
            {"value_id": 5004, "name": "Boho"},
            {"value_id": 5005, "name": "Minimalist"},
            {"value_id": 5006, "name": "Rustic"},
        ],
    },
]


def suggest_taxonomy_properties(
    title: str,
    description: str,
    tags: list[str] | None = None,
    available_properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministically suggest property values based on listing concept & keywords."""
    corpus = f"{title} {description} {' '.join(tags or [])}".lower()
    props_to_check = available_properties if available_properties else STANDARD_DIGITAL_PROPERTIES

    suggested: dict[str, Any] = {}

    for prop in props_to_check:
        prop_name = str(prop.get("name", ""))
        prop_id = prop.get("property_id")
        possible_values = prop.get("possible_values", [])

        if not prop_id or not possible_values:
            continue

        prop_name_lower = prop_name.lower()

        # Craft type (Default Sublimation + Printing & printmaking for digital PNG design downloads)
        if "craft" in prop_name_lower:
            selected_val_ids: list[int] = []
            selected_val_names: list[str] = []
            for val in possible_values:
                val_name = str(val.get("name", ""))
                val_id = val.get("value_id")
                if "sublimation" in val_name.lower() or "print" in val_name.lower() or "direct to garment" in val_name.lower():
                    if val_id:
                        selected_val_ids.append(int(val_id))
                        selected_val_names.append(val_name)
            # Fallback if specific values weren't matched
            if not selected_val_ids and possible_values:
                first_val = possible_values[0]
                if first_val.get("value_id"):
                    selected_val_ids.append(int(first_val["value_id"]))
                    selected_val_names.append(str(first_val.get("name", "")))

            if selected_val_ids:
                suggested[str(prop_id)] = {
                    "property_id": prop_id,
                    "property_name": prop_name,
                    "value_ids": selected_val_ids,
                    "values": selected_val_names,
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
                        "is_suggested": True,
                    }
                    break

        # Primary color
        elif "primary color" in prop_name_lower:
            color_keywords = ["brown", "red", "green", "black", "white", "blue", "orange", "pink", "beige"]
            for color in color_keywords:
                if color in corpus:
                    for val in possible_values:
                        if val.get("name", "").lower() == color:
                            suggested[str(prop_id)] = {
                                "property_id": prop_id,
                                "property_name": prop_name,
                                "value_ids": [int(val["value_id"])] if val.get("value_id") else [],
                                "values": [val["name"]],
                                "is_suggested": True,
                            }
                            break
                    if str(prop_id) in suggested:
                        break

    return suggested
