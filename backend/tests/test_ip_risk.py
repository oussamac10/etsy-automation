"""Preliminary phrase screen.

The screen is crude on purpose, so these tests pin what it does and does not
claim: it catches obvious brand names anywhere in the text it is given, and a
clean result is never evidence that a phrase is safe.
"""

from __future__ import annotations

from app.domain import ip_risk


class TestScan:
    def test_clean_text_flags_nothing(self) -> None:
        assert ip_risk.scan("Sleepy fox on a mug", "Cosy autumn illustration") == []

    def test_flags_a_brand_name_case_insensitively(self) -> None:
        assert ip_risk.scan("DISNEY castle silhouette") == ["disney"]

    def test_flags_a_multi_word_term(self) -> None:
        assert ip_risk.scan("a tribute to Taylor Swift") == ["taylor swift"]

    def test_matches_inside_a_longer_word(self) -> None:
        # "disneyland" must be as loud as "disney"; a word-boundary match would
        # let the most common evasion straight through.
        assert ip_risk.scan("disneyland vacation png") == ["disney"]

    def test_scans_all_parts_as_one_phrase(self) -> None:
        # The term is split across two arguments: scanning parts separately
        # would miss it.
        assert ip_risk.scan("a tribute to taylor", "swift energy") == ["taylor swift"]

    def test_ignores_missing_parts(self) -> None:
        assert ip_risk.scan(None, "", "harmless phrase") == []

    def test_returns_every_distinct_term_found(self) -> None:
        found = ip_risk.scan("nike and barbie crossover")
        assert set(found) == {"nike", "barbie"}
