"""Shop section suggestions and normalization for Etsy listings."""

from __future__ import annotations

import re


def normalize_section_title(title: str) -> str:
    """Normalize a shop section title to prevent near-duplicate sections.

    - Strips whitespace
    - Normalizes internal spacing
    - Converts title case
    """
    clean = re.sub(r"\s+", " ", title.strip())
    return clean.title()


def _stem_simple(text: str) -> str:
    """Simple stemmer removing trailing 's' / 'es' / 'png' / 'pngs' for fuzzy section matching."""
    s = text.lower().strip()
    s = re.sub(r"(\s+pngs?|\s+cliparts?|\s+designs?|\s+files?)$", "", s)
    if s.endswith("es") and len(s) > 4:
        s = s[:-2]
    elif s.endswith("s") and not s.endswith("ss") and len(s) > 3:
        s = s[:-1]
    return s


def find_matching_existing_section(
    suggested_title: str,
    existing_sections: list[dict[str, object]],
) -> tuple[str | None, str | None]:
    """Check if an existing shop section matches the suggested title.

    Returns (section_id, section_title) if match found, else (None, None).
    """
    suggested_stem = _stem_simple(suggested_title)

    for sec in existing_sections:
        sec_title = str(sec.get("title", "")).strip()
        sec_id = str(sec.get("shop_section_id") or sec.get("id") or "")
        if not sec_title:
            continue

        if sec_title.lower() == suggested_title.lower():
            return sec_id, sec_title

        if _stem_simple(sec_title) == suggested_stem:
            return sec_id, sec_title

    return None, None


def suggest_shop_section_title(
    title: str,
    tags: list[str] | None = None,
    existing_sections: list[dict[str, object]] | None = None,
) -> tuple[str, str | None]:
    """Suggest an appropriate shop section title for a digital listing.

    Returns (suggested_section_name, matching_existing_section_id).
    """
    corpus = f"{title} {' '.join(tags or [])}".lower()

    # Rule-based thematic mapping
    if any(k in corpus for k in ("christmas", "xmas", "santa", "gingerbread", "holiday", "winter")):
        suggestion = "Christmas PNGs"
    elif any(k in corpus for k in ("halloween", "spooky", "witch", "ghost", "pumpkin")):
        suggestion = "Halloween PNGs"
    elif any(k in corpus for k in ("fall", "autumn", "thanksgiving", "cozy")):
        suggestion = "Fall PNGs"
    elif any(k in corpus for k in ("book", "reading", "reader", "library", "bookish")):
        suggestion = "Book Lover PNGs"
    elif any(k in corpus for k in ("mushroom", "cottagecore", "nature", "forest", "botanical", "flower", "floral")):
        suggestion = "Botanical & Cottagecore"
    elif any(k in corpus for k in ("mama", "mom", "mother", "family", "baby")):
        suggestion = "Family & Mama PNGs"
    elif any(k in corpus for k in ("retro", "vintage", "70s", "80s", "groovy", "western", "cowgirl")):
        suggestion = "Retro & Vintage"
    elif any(k in corpus for k in ("coffee", "baking", "food", "tea", "cook")):
        suggestion = "Food & Coffee PNGs"
    elif any(k in corpus for k in ("dog", "cat", "pet", "animal")):
        suggestion = "Pet & Animal PNGs"
    else:
        suggestion = "Digital PNG Downloads"

    # Match against existing shop sections if available
    matched_id = None
    if existing_sections:
        sec_id, matched_name = find_matching_existing_section(suggestion, existing_sections)
        if sec_id and matched_name:
            return matched_name, sec_id

    return suggestion, matched_id
