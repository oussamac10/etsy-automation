"""Etsy tag normalization and validation rules.

Matches the constraints defined in packages/domain/src/tags.ts:
- Max 13 tags.
- Max 20 characters per tag.
- Max 140 characters for title.
- Allowed characters: Letters, digits, spaces, hyphens, and apostrophes.
- Trimming and duplicate rejection after normalization.
"""

from __future__ import annotations

import re
from typing import Final

MAX_ETSY_TAGS: Final[int] = 13
MAX_TAG_LENGTH: Final[int] = 20
MAX_TITLE_LENGTH: Final[int] = 140

# Letters, digits, spaces, hyphens, apostrophes
ALLOWED_TAG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[\w][\w\s\-']*$", re.UNICODE)


def normalize_tag(raw: str) -> str:
    """Trim, collapse multiple spaces, and convert to lower-case."""
    return re.sub(r"\s+", " ", raw.strip()).lower()


def validate_tags(raw_tags: list[str]) -> tuple[bool, list[str], list[str]]:
    """Validate a list of tags against Etsy constraints.

    Returns:
        tuple[is_valid, accepted_tags, error_messages]
    """
    errors: list[str] = []
    accepted: list[str] = []
    seen: set[str] = set()

    for raw in raw_tags:
        tag = normalize_tag(raw)
        if not tag:
            errors.append("Empty tag is not allowed.")
            continue
        if len(tag) > MAX_TAG_LENGTH:
            errors.append(f'Tag "{tag}" exceeds {MAX_TAG_LENGTH} characters.')
            continue
        if not ALLOWED_TAG_PATTERN.match(tag):
            errors.append(f'Tag "{tag}" contains unsupported characters.')
            continue
        if tag in seen:
            errors.append(f'Tag "{tag}" is duplicated after normalization.')
            continue

        seen.add(tag)
        accepted.append(tag)

    if len(accepted) != MAX_ETSY_TAGS:
        errors.append(
            f"Exactly {MAX_ETSY_TAGS} tags required: got {len(accepted)} accepted tags."
        )

    return len(errors) == 0, accepted, errors


def validate_listing_title(raw_title: str) -> tuple[bool, str | None]:
    """Validate Etsy listing title.

    Returns:
        tuple[is_valid, error_message]
    """
    title = raw_title.strip()
    if not title:
        return False, "Listing title cannot be empty."
    if len(title) > MAX_TITLE_LENGTH:
        return False, f"Listing title exceeds {MAX_TITLE_LENGTH} characters (got {len(title)})."
    return True, None
