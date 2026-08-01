"""Rules for the three idea input modes.

The product promise is narrow and worth stating exactly: **the owner's own words
are never overwritten.** An optimised concept is a new, separately-stored row
that points back at the original. A correction is a new revision, not an edit.

This module holds the rules; ``app/infrastructure/models/idea.py`` holds the
storage that enforces them at the database level.
"""

from __future__ import annotations

import re
import unicodedata

from app.domain.enums import ConceptOrigin, IdeaMode
from app.domain.errors import InvalidIdeaModeError

#: Modes that require the owner to supply text.
MODES_REQUIRING_IDEA: frozenset[IdeaMode] = frozenset({IdeaMode.USER_IDEA, IdeaMode.HYBRID})

#: Which concept origins each mode may legitimately produce.
ALLOWED_ORIGINS: dict[IdeaMode, frozenset[ConceptOrigin]] = {
    # No personal idea exists, so nothing may claim to have come from one.
    IdeaMode.MARKET_LED: frozenset({ConceptOrigin.MARKET}),
    # The owner's concept is the point. Market-only proposals would defeat it.
    IdeaMode.USER_IDEA: frozenset({ConceptOrigin.USER}),
    # The whole purpose of hybrid is to hold all three side by side.
    IdeaMode.HYBRID: frozenset({ConceptOrigin.USER, ConceptOrigin.MARKET, ConceptOrigin.HYBRID}),
}

MIN_IDEA_LENGTH = 3
MAX_IDEA_LENGTH = 4000


def requires_original_idea(mode: IdeaMode) -> bool:
    """True when the mode cannot start without the owner's own text."""
    return mode in MODES_REQUIRING_IDEA


def validate_idea_submission(mode: IdeaMode, original_text: str | None) -> None:
    """Check a submission against its mode.

    ``market-led`` explicitly refuses text: accepting it would create an
    expectation that research preserves something the mode does not track.
    """
    has_text = original_text is not None and original_text.strip() != ""

    if requires_original_idea(mode) and not has_text:
        raise InvalidIdeaModeError(
            mode, "an original idea is required for this mode but none was supplied"
        )
    if not requires_original_idea(mode) and has_text:
        raise InvalidIdeaModeError(
            mode,
            "this mode starts from market research only; submit an idea with "
            "'user-idea' or 'hybrid' instead",
        )
    if has_text:
        assert original_text is not None  # narrowed by has_text
        stripped = original_text.strip()
        if len(stripped) < MIN_IDEA_LENGTH:
            raise InvalidIdeaModeError(
                mode, f"the idea must be at least {MIN_IDEA_LENGTH} characters"
            )
        if len(original_text) > MAX_IDEA_LENGTH:
            raise InvalidIdeaModeError(
                mode, f"the idea must be at most {MAX_IDEA_LENGTH} characters"
            )


def validate_concept_origin(mode: IdeaMode, origin: ConceptOrigin) -> None:
    """Refuse a concept whose claimed origin is impossible for the mode."""
    if origin not in ALLOWED_ORIGINS[mode]:
        allowed = ", ".join(sorted(ALLOWED_ORIGINS[mode]))
        raise InvalidIdeaModeError(
            mode, f"origin {origin!r} is not valid for this mode; allowed: {allowed}"
        )


def normalize_idea_text(text: str) -> str:
    """A comparison form of the idea text.

    Stored **beside** the verbatim original, never instead of it. Used for
    duplicate detection and search; the original column is what is shown back to
    the owner and what any "unchanged" assertion is made against.
    """
    normalized = unicodedata.normalize("NFKC", text)
    # The escapes are the curly quotes themselves; folding them is the point.
    normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().casefold()


def is_faithful_to_original(original: str, candidate: str) -> bool:
    """True when ``candidate`` still carries the original's exact wording.

    Used by tests and by the Phase 5 research step to assert that the preserved
    record was not quietly replaced by an optimised rewrite. It compares
    normalised text, so punctuation and whitespace differences are tolerated but
    a reworded concept is not.
    """
    return normalize_idea_text(original) == normalize_idea_text(candidate)
