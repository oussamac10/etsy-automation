"""Idea mode rules and the preservation promise."""

from __future__ import annotations

import pytest

from app.domain.enums import ConceptOrigin, IdeaMode
from app.domain.errors import InvalidIdeaModeError
from app.domain.ideas import (
    ALLOWED_ORIGINS,
    is_faithful_to_original,
    normalize_idea_text,
    requires_original_idea,
    validate_concept_origin,
    validate_idea_submission,
)

ORIGINAL = (
    "A hand-drawn sleepy fox curled around a steaming mug, for people who love "
    "quiet autumn mornings."
)


class TestModes:
    def test_there_are_exactly_three_modes(self) -> None:
        assert {mode.value for mode in IdeaMode} == {
            "market-led",
            "user-idea",
            "hybrid",
        }

    @pytest.mark.parametrize(
        ("mode", "required"),
        [
            (IdeaMode.MARKET_LED, False),
            (IdeaMode.USER_IDEA, True),
            (IdeaMode.HYBRID, True),
        ],
    )
    def test_which_modes_require_an_idea(self, mode: IdeaMode, required: bool) -> None:
        assert requires_original_idea(mode) is required


class TestSubmissionValidation:
    def test_market_led_accepts_no_idea(self) -> None:
        validate_idea_submission(IdeaMode.MARKET_LED, None)

    def test_market_led_refuses_an_idea(self) -> None:
        """Accepting text here would imply a preservation promise the mode does not make."""
        with pytest.raises(InvalidIdeaModeError, match="market research only"):
            validate_idea_submission(IdeaMode.MARKET_LED, ORIGINAL)

    @pytest.mark.parametrize("mode", [IdeaMode.USER_IDEA, IdeaMode.HYBRID])
    def test_idea_modes_require_text(self, mode: IdeaMode) -> None:
        with pytest.raises(InvalidIdeaModeError, match="required"):
            validate_idea_submission(mode, None)
        with pytest.raises(InvalidIdeaModeError, match="required"):
            validate_idea_submission(mode, "   ")

    @pytest.mark.parametrize("mode", [IdeaMode.USER_IDEA, IdeaMode.HYBRID])
    def test_idea_modes_accept_text(self, mode: IdeaMode) -> None:
        validate_idea_submission(mode, ORIGINAL)

    def test_too_short_is_rejected(self) -> None:
        with pytest.raises(InvalidIdeaModeError, match="at least"):
            validate_idea_submission(IdeaMode.USER_IDEA, "ab")

    def test_too_long_is_rejected(self) -> None:
        with pytest.raises(InvalidIdeaModeError, match="at most"):
            validate_idea_submission(IdeaMode.USER_IDEA, "x" * 4001)


class TestConceptOrigin:
    def test_market_led_may_only_produce_market_concepts(self) -> None:
        validate_concept_origin(IdeaMode.MARKET_LED, ConceptOrigin.MARKET)
        for origin in (ConceptOrigin.USER, ConceptOrigin.HYBRID):
            with pytest.raises(InvalidIdeaModeError):
                validate_concept_origin(IdeaMode.MARKET_LED, origin)

    def test_user_idea_may_only_produce_user_concepts(self) -> None:
        validate_concept_origin(IdeaMode.USER_IDEA, ConceptOrigin.USER)
        for origin in (ConceptOrigin.MARKET, ConceptOrigin.HYBRID):
            with pytest.raises(InvalidIdeaModeError):
                validate_concept_origin(IdeaMode.USER_IDEA, origin)

    def test_hybrid_may_produce_all_three(self) -> None:
        for origin in ConceptOrigin:
            validate_concept_origin(IdeaMode.HYBRID, origin)

    def test_every_mode_has_at_least_one_allowed_origin(self) -> None:
        for mode in IdeaMode:
            assert ALLOWED_ORIGINS[mode]


class TestNormalisation:
    def test_normalisation_is_for_comparison_only(self) -> None:
        """The normalised form is stored beside the original, never instead of it."""
        normalised = normalize_idea_text("  A  Sleepy   FOX  ")
        assert normalised == "a sleepy fox"

    def test_curly_apostrophes_are_folded(self) -> None:
        assert normalize_idea_text("don\u2019t") == normalize_idea_text("don't")

    def test_unicode_is_normalised(self) -> None:
        assert normalize_idea_text("ﬁsh") == normalize_idea_text("fish")


class TestFaithfulness:
    def test_identical_text_is_faithful(self) -> None:
        assert is_faithful_to_original(ORIGINAL, ORIGINAL)

    def test_whitespace_and_case_differences_are_tolerated(self) -> None:
        assert is_faithful_to_original(ORIGINAL, f"  {ORIGINAL.upper()}  ")

    def test_a_reworded_concept_is_not_faithful(self) -> None:
        """This is the check that catches an optimised rewrite pretending to be the original."""
        optimised = "Cozy Autumn Fox PNG | Sleepy Fox With Coffee Mug | Fall Sublimation Design"
        assert not is_faithful_to_original(ORIGINAL, optimised)

    def test_a_truncated_idea_is_not_faithful(self) -> None:
        assert not is_faithful_to_original(ORIGINAL, ORIGINAL[:40])
