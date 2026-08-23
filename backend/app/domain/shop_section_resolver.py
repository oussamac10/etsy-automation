"""Shop section suggestions and normalization for Etsy listings."""

from __future__ import annotations

import re
from typing import Any


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
    existing_sections: list[dict[str, Any]],
    corpus: str = "",
) -> tuple[str | None, str | None]:
    """Check if an existing shop section matches the suggested title or listing corpus.

    Returns (section_id, section_title) if match found, else (None, None).
    """
    suggested_stem = _stem_simple(suggested_title)
    corpus_lower = corpus.lower()

    # 1. Exact or stemmed match on suggested title
    for sec in existing_sections:
        sec_title = str(sec.get("title", "")).strip()
        sec_id = str(sec.get("shop_section_id") or sec.get("id") or "")
        if not sec_title or not sec_id:
            continue

        if sec_title.lower() == suggested_title.lower():
            return sec_id, sec_title

        sec_stem = _stem_simple(sec_title)
        if sec_stem == suggested_stem:
            return sec_id, sec_title

    # 2. Containment / word intersection match between existing section and suggested title
    for sec in existing_sections:
        sec_title = str(sec.get("title", "")).strip()
        sec_id = str(sec.get("shop_section_id") or sec.get("id") or "")
        if not sec_title or not sec_id:
            continue

        sec_stem = _stem_simple(sec_title)
        if sec_stem and (sec_stem in suggested_stem or suggested_stem in sec_stem):
            return sec_id, sec_title

        sec_words = set(re.findall(r"[a-z0-9]+", sec_stem))
        sug_words = set(re.findall(r"[a-z0-9]+", suggested_stem))
        common = sec_words & sug_words - {
            "png",
            "pngs",
            "clipart",
            "design",
            "designs",
            "download",
            "downloads",
            "and",
        }
        if common:
            return sec_id, sec_title

    # 3. Direct match of existing section keywords in the listing corpus
    if corpus_lower:
        for sec in existing_sections:
            sec_title = str(sec.get("title", "")).strip()
            sec_id = str(sec.get("shop_section_id") or sec.get("id") or "")
            if not sec_title or not sec_id:
                continue

            sec_stem = _stem_simple(sec_title)
            sec_words_list = [
                w
                for w in re.findall(r"[a-z0-9]+", sec_stem)
                if len(w) > 3
                and w
                not in {"png", "pngs", "clipart", "design", "designs", "download", "downloads"}
            ]
            if sec_words_list and all(w in corpus_lower for w in sec_words_list):
                return sec_id, sec_title

    return None, None


def suggest_shop_section_title(
    title: str,
    tags: list[str] | None = None,
    existing_sections: list[dict[str, Any]] | None = None,
) -> tuple[str, str | None]:
    """Suggest an appropriate shop section title for a digital listing.

    Returns (suggested_section_name, matching_existing_section_id).
    """
    corpus = f"{title} {' '.join(tags or [])}".lower()

    # Rule-based thematic mapping
    if any(
        k in corpus
        for k in (
            "christmas",
            "xmas",
            "santa",
            "gingerbread",
            "holiday",
            "winter",
            "snowman",
            "reindeer",
            "nutcracker",
            "noel",
        )
    ):
        suggestion = "Christmas PNGs"
    elif any(
        k in corpus
        for k in (
            "halloween",
            "spooky",
            "witch",
            "ghost",
            "pumpkin",
            "skeleton",
            "skull",
            "bat",
            "vampire",
            "horror",
            "ghoul",
            "haunted",
        )
    ):
        suggestion = "Halloween PNGs"
    elif any(
        k in corpus
        for k in ("fall", "autumn", "thanksgiving", "harvest", "cozy", "hayride", "flannel")
    ):
        suggestion = "Fall PNGs"
    elif any(
        k in corpus
        for k in (
            "cow",
            "calf",
            "highland cow",
            "cattle",
            "bull",
            "heifer",
            "dog",
            "puppy",
            "cat",
            "kitten",
            "pet",
            "pets",
            "animal",
            "animals",
            "bear",
            "deer",
            "horse",
            "pony",
            "pig",
            "piglet",
            "sheep",
            "lamb",
            "duck",
            "chicken",
            "rooster",
            "bunny",
            "rabbit",
            "wildlife",
            "safari",
            "zoo",
            "sloth",
            "llama",
            "alpaca",
            "fox",
            "owl",
            "bird",
            "elephant",
            "lion",
            "tiger",
            "giraffe",
            "farm",
            "barn",
        )
    ):
        suggestion = "Pet & Animal PNGs"
    elif any(
        k in corpus
        for k in (
            "teacher",
            "school",
            "classroom",
            "student",
            "teach",
            "teaching",
            "educator",
            "kindergarten",
            "preschool",
            "grade",
            "back to school",
            "pencil",
            "chalkboard",
            "counselor",
            "principal",
            "librarian",
            "study",
            "academic",
        )
    ):
        suggestion = "Teacher & School PNGs"
    elif any(
        k in corpus
        for k in (
            "nurse",
            "nursing",
            "doctor",
            "medical",
            "medicine",
            "hospital",
            "healthcare",
            "pharma",
            "scrub",
            "stethoscope",
            "rn",
            "cna",
            "medic",
            "pharmacy",
            "clinic",
        )
    ):
        suggestion = "Medical & Nurse PNGs"
    elif any(
        k in corpus
        for k in (
            "mushroom",
            "cottagecore",
            "nature",
            "forest",
            "botanical",
            "flower",
            "floral",
            "plant",
            "garden",
            "wildflower",
            "succulent",
            "leaves",
            "herb",
        )
    ):
        suggestion = "Botanical & Cottagecore"
    elif any(
        k in corpus
        for k in (
            "book",
            "reading",
            "reader",
            "library",
            "bookish",
            "bookworm",
            "literature",
            "novel",
            "books",
        )
    ):
        suggestion = "Book Lover PNGs"
    elif any(
        k in corpus
        for k in (
            "coffee",
            "iced coffee",
            "latte",
            "espresso",
            "tea",
            "baking",
            "bakery",
            "food",
            "drink",
            "cook",
            "chef",
            "cocktail",
            "beer",
            "wine",
            "snack",
            "cookie",
            "kitchen",
        )
    ):
        suggestion = "Food & Coffee PNGs"
    elif any(
        k in corpus
        for k in (
            "mama",
            "mom",
            "mother",
            "dad",
            "father",
            "family",
            "sister",
            "brother",
            "grandma",
            "grandpa",
            "aunt",
            "uncle",
            "parent",
        )
    ):
        suggestion = "Family & Mama PNGs"
    elif any(
        k in corpus
        for k in (
            "western",
            "cowboy",
            "cowgirl",
            "rodeo",
            "howdy",
            "yall",
            "boots",
            "retro",
            "vintage",
            "70s",
            "80s",
            "90s",
            "groovy",
            "disco",
        )
    ):
        suggestion = "Retro & Western"
    else:
        suggestion = "Digital PNG Downloads"

    # Match against existing shop sections if available
    matched_id = None
    if existing_sections:
        sec_id, matched_name = find_matching_existing_section(
            suggestion, existing_sections, corpus=corpus
        )
        if sec_id and matched_name:
            return matched_name, sec_id

    return suggestion, matched_id
