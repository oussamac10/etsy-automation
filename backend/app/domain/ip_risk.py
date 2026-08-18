"""Preliminary phrase and trademark IP screening engine.

Provides automated preliminary trademark screening against USPTO data and internal
keyword dictionaries. This is a preliminary screening tool and NOT legal advice.

Classification vocabulary:
- LOW: No active/live trademark matches discovered in relevant classes.
- MEDIUM (Warning): Similar marks or live marks with potential/ambiguous goods overlap;
  requires explicit user acknowledgement before Gate 3 approval.
- HIGH (High Risk): Exact or highly similar live marks in apparel, downloadable graphics,
  or print-on-demand goods/services. Strictly blocks Gate 3 approval until edited/regenerated.
"""

from __future__ import annotations

import re
from typing import Any, Final

from app.domain.workflow import RiskLevel

#: Lower-case substrings that must never appear in a generated concept.
FLAGGED_TERMS: Final[tuple[str, ...]] = (
    "disney",
    "marvel",
    "starbucks",
    "taylor swift",
    "star wars",
    "harry potter",
    "nike",
    "barbie",
)

#: Nice International Classes most relevant to Etsy print-on-demand & digital PNGs.
RELEVANT_POD_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "009",  # Downloadable graphics, digital art, computer software
        "016",  # Paper goods, printed materials, stickers, posters
        "021",  # Household goods, mugs, tumblers, drinkware
        "025",  # Clothing, footwear, headwear, t-shirts, sweatshirts, hoodies
        "035",  # Retail store services, e-commerce, advertising
    }
)

RELEVANT_GOODS_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "shirt",
        "clothing",
        "apparel",
        "graphic",
        "downloadable",
        "digital",
        "poster",
        "sticker",
        "mug",
        "tumbler",
        "print",
        "tote",
        "decal",
        "merchandise",
    }
)


def normalize_trademark_phrase(raw: str) -> str:
    """Normalize a phrase for trademark searching.

    Lowercases, strips punctuation, and collapses multiple whitespaces.
    """
    cleaned = re.sub(r"[^\w\s]", "", raw.strip()).lower()
    return re.sub(r"\s+", " ", cleaned)


def extract_searchable_phrases(
    slogan: str | None,
    title: str | None,
    keywords: list[str] | None,
    tags: list[str] | None,
) -> list[str]:
    """Extract and deduplicate unique searchable phrases from listing assets."""
    candidates: list[str] = []

    if slogan:
        candidates.append(slogan)
    if title:
        candidates.append(title)
        # Also split title on separators like |, -, commas to extract key phrases
        for chunk in re.split(r"[,|\-–—:]", title):
            chunk_trimmed = chunk.strip()
            if len(chunk_trimmed) >= 3:
                candidates.append(chunk_trimmed)

    if keywords:
        candidates.extend(keywords)
    if tags:
        candidates.extend(tags)

    normalized_seen: set[str] = set()
    result: list[str] = []

    for item in candidates:
        norm = normalize_trademark_phrase(item)
        # Skip trivial single-character terms or common stopwords
        if len(norm) < 3 or norm in {"and", "the", "for", "with", "png", "svg", "eps", "dxf"}:
            continue
        if norm not in normalized_seen:
            normalized_seen.add(norm)
            result.append(item.strip())

    return result


def is_goods_overlap(classes: list[str] | None, goods_services: str | None) -> bool:
    """Check whether a mark covers Nice classes or descriptions relevant to POD."""
    if classes:
        # Normalize classes to 3 digits e.g. "25" -> "025"
        for cls_code in classes:
            padded = cls_code.zfill(3)
            if padded in RELEVANT_POD_CLASSES:
                return True

    if goods_services:
        gs_lower = goods_services.lower()
        for kw in RELEVANT_GOODS_KEYWORDS:
            if kw in gs_lower:
                return True

    return False


def evaluate_trademark_risk(
    searched_phrases: list[str],
    matches: list[dict[str, Any]],
) -> tuple[RiskLevel, dict[str, Any]]:
    """Determine overall trademark risk and generate structured findings.

    Args:
        searched_phrases: List of input phrases queried.
        matches: Normalized match dictionaries containing:
                 - mark_text: str
                 - serial_number: str | None
                 - registration_number: str | None
                 - is_live: bool
                 - classes: list[str]
                 - goods_services: str | None
                 - owner: str | None
                 - status: str

    Returns:
        tuple[RiskLevel, findings_dict]
    """
    flagged_kw = scan(*searched_phrases)

    findings: list[dict[str, Any]] = []
    has_high_risk = False
    has_warning = False

    # Check hardcoded high-risk flagged terms
    for term in flagged_kw:
        findings.append(
            {
                "searched_phrase": term,
                "matched_mark": term.upper(),
                "match_type": "KNOWN_RESTRICTED_BRAND",
                "is_live": True,
                "classes": ["025", "009"],
                "goods_services": "Known high-risk brand / character franchise",
                "risk_reason": f'Contains known restricted commercial brand "{term.title()}".',
                "recommended_action": (
                    "Remove this term from the slogan, title, or tags before listing."
                ),
            }
        )
        has_high_risk = True

    # Evaluate USPTO matches
    for match in matches:
        mark_text = match.get("mark_text", "")
        norm_mark = normalize_trademark_phrase(mark_text)
        is_live = bool(match.get("is_live", False))
        classes = match.get("classes", [])
        goods_services = match.get("goods_services", "")
        serial_number = match.get("serial_number")
        registration_number = match.get("registration_number")
        owner = match.get("owner")

        overlap = is_goods_overlap(classes, goods_services)

        # Check exact vs partial match against searched phrases
        is_exact = any(norm_mark == normalize_trademark_phrase(p) for p in searched_phrases)
        is_contained = any(
            norm_mark in normalize_trademark_phrase(p)
            or normalize_trademark_phrase(p) in norm_mark
            for p in searched_phrases
        )

        if not is_live:
            # Dead marks are informative but do not trigger High Risk
            findings.append(
                {
                    "searched_phrase": mark_text,
                    "matched_mark": mark_text,
                    "match_type": "DEAD_MARK",
                    "is_live": False,
                    "serial_number": serial_number,
                    "registration_number": registration_number,
                    "classes": classes,
                    "goods_services": goods_services,
                    "owner": owner,
                    "risk_reason": "Registered mark is DEAD/cancelled.",
                    "recommended_action": "Informational record; mark is inactive.",
                }
            )
            continue

        if is_exact and overlap:
            has_high_risk = True
            risk_reason = (
                f'Exact LIVE trademark match for "{mark_text}" in relevant apparel/digital '
                f'classes ({", ".join(classes) if classes else "POD overlap"}).'
            )
            rec_action = (
                "Do not use this phrase. Change the artwork slogan or listing tags to proceed."
            )
            findings.append(
                {
                    "searched_phrase": mark_text,
                    "matched_mark": mark_text,
                    "match_type": "EXACT_LIVE_POD_OVERLAP",
                    "is_live": True,
                    "serial_number": serial_number,
                    "registration_number": registration_number,
                    "classes": classes,
                    "goods_services": goods_services,
                    "owner": owner,
                    "risk_reason": risk_reason,
                    "recommended_action": rec_action,
                }
            )
        elif is_exact and not overlap:
            has_warning = True
            risk_reason = (
                f'Exact LIVE trademark match for "{mark_text}", but registered in unrelated '
                f'classes ({", ".join(classes)}).'
            )
            rec_action = "Review goods/services description. Acknowledge risk to proceed."
            findings.append(
                {
                    "searched_phrase": mark_text,
                    "matched_mark": mark_text,
                    "match_type": "EXACT_LIVE_UNRELATED_CLASS",
                    "is_live": True,
                    "serial_number": serial_number,
                    "registration_number": registration_number,
                    "classes": classes,
                    "goods_services": goods_services,
                    "owner": owner,
                    "risk_reason": risk_reason,
                    "recommended_action": rec_action,
                }
            )
        elif is_contained:
            has_warning = True
            risk_reason = f'Partial LIVE mark overlap with "{mark_text}".'
            rec_action = "Inspect phrase context. Acknowledge warning if distinct."
            findings.append(
                {
                    "searched_phrase": mark_text,
                    "matched_mark": mark_text,
                    "match_type": "PARTIAL_LIVE_OVERLAP",
                    "is_live": True,
                    "serial_number": serial_number,
                    "registration_number": registration_number,
                    "classes": classes,
                    "goods_services": goods_services,
                    "owner": owner,
                    "risk_reason": risk_reason,
                    "recommended_action": rec_action,
                }
            )

    if has_high_risk:
        overall_level = RiskLevel.HIGH
    elif has_warning:
        overall_level = RiskLevel.MEDIUM
    else:
        overall_level = RiskLevel.LOW

    structured_findings = {
        "searched_phrases": searched_phrases,
        "match_count": len(findings),
        "findings": findings,
        "disclaimer": "Preliminary automated trademark screening only — not legal advice.",
        "requires_acknowledgement": overall_level == RiskLevel.MEDIUM,
        "blocks_approval": overall_level == RiskLevel.HIGH,
    }

    return overall_level, structured_findings


def scan(*parts: str | None) -> list[str]:
    """Return every flagged term found across ``parts``, in declaration order."""
    haystack = " ".join(part for part in parts if part).lower()
    return [term for term in FLAGGED_TERMS if term in haystack]
