"""Preliminary phrase/IP screening.

This is a deliberately crude keyword screen, not a trademark search. It exists
so that an obviously infringing phrase never reaches a human gate wearing a
``low`` risk badge. A clean result means "nothing obvious was spotted"; it
never means the phrase is cleared, and no caller may present it that way.

A real ``TrademarkDataGateway`` lookup lands in Phase 8; this screen stays
regardless, because it is free and catches the loudest mistakes before any
paid call.
"""

from __future__ import annotations

from typing import Final

#: Lower-case substrings that must never appear in a generated concept. Brands,
#: franchises and public figures whose names alone signal an infringement risk.
#: Substring matching is intentional: "disneyland" must flag as loudly as
#: "disney".
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


def scan(*parts: str | None) -> list[str]:
    """Return every flagged term found across ``parts``, in declaration order.

    Parts are joined rather than scanned separately so that a term split across
    a title and a slogan is still caught as one phrase.
    """
    haystack = " ".join(part for part in parts if part).lower()
    return [term for term in FLAGGED_TERMS if term in haystack]
