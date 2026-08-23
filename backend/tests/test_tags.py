"""Tests for Etsy tag and title validation rules."""

from app.domain.tags import (
    normalize_tag,
    validate_listing_title,
    validate_tags,
)


class TestTagsDomain:
    def test_normalize_tag_lowercases_and_strips(self) -> None:
        assert normalize_tag("  Cool  T-Shirt PNG!  ") == "cool t-shirt png!"
        assert normalize_tag("MUSHROOM 1") == "mushroom 1"
        assert normalize_tag("aesthetic-art") == "aesthetic-art"

    def test_validate_tags_accepts_exactly_13_valid_tags(self) -> None:
        tags = [
            "png download",
            "tshirt design",
            "sublimation graphic",
            "vintage mushroom",
            "cottagecore art",
            "retro vibes",
            "digital print",
            "clipart file",
            "dtg ready",
            "shirt sublimation",
            "mug graphic",
            "transparent png",
            "commercial use",
        ]
        is_valid, accepted, errors = validate_tags(tags)
        assert is_valid is True
        assert len(accepted) == 13
        assert len(errors) == 0

    def test_validate_tags_rejects_under_13_tags(self) -> None:
        tags = ["tag1", "tag2", "tag3"]
        is_valid, accepted, errors = validate_tags(tags)
        assert is_valid is False
        assert any("Exactly 13 tags required" in err for err in errors)

    def test_validate_tags_rejects_over_13_tags(self) -> None:
        tags = [f"tag-{i}" for i in range(14)]
        is_valid, accepted, errors = validate_tags(tags)
        assert is_valid is False
        assert any("Exactly 13 tags required" in err for err in errors)

    def test_validate_tags_rejects_tags_longer_than_20_chars(self) -> None:
        tags = [f"tag-{i}" for i in range(12)] + ["this tag is way too long for etsy"]
        is_valid, accepted, errors = validate_tags(tags)
        assert is_valid is False
        assert any("exceeds 20 characters" in err for err in errors)

    def test_validate_tags_rejects_duplicate_tags(self) -> None:
        tags = ["vintage mushroom", "vintage  mushroom"] + [f"tag-{i}" for i in range(11)]
        is_valid, accepted, errors = validate_tags(tags)
        assert is_valid is False
        assert any("duplicated after normalization" in err for err in errors)

    def test_validate_listing_title(self) -> None:
        valid_title = "Cute Vintage Mushroom PNG Digital Download, Cottagecore Botanical Sublimation T-Shirt Design"
        is_valid, err = validate_listing_title(valid_title)
        assert is_valid is True
        assert err is None

        blank_title = "   "
        is_valid, err = validate_listing_title(blank_title)
        assert is_valid is False
        assert "cannot be empty" in (err or "")

        too_long_title = "A" * 141
        is_valid, err = validate_listing_title(too_long_title)
        assert is_valid is False
        assert "exceeds 140 characters" in (err or "")
