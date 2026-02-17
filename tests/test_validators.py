"""Tests for text validators (banned/risk term scanning)."""

from __future__ import annotations

from app.utils.validators import (
    scan_for_banned_terms,
    scan_for_risk_terms,
    validate_text_content,
)


class TestScanForBannedTerms:
    def test_finds_banned_term(self):
        result = scan_for_banned_terms("This shirt promotes murder vibes")
        assert "murder" in result

    def test_no_banned_terms(self):
        result = scan_for_banned_terms("Funny cat t-shirt design")
        assert result == []

    def test_case_insensitive(self):
        result = scan_for_banned_terms("MURDER is bad")
        assert "murder" in result


class TestScanForRiskTerms:
    def test_finds_trademark(self):
        result = scan_for_risk_terms("Cool nike style design")
        assert "nike" in result

    def test_finds_celebrity(self):
        result = scan_for_risk_terms("Taylor Swift fan tee")
        assert "taylor swift" in result

    def test_no_risk_terms(self):
        result = scan_for_risk_terms("Retro gaming pixel art design")
        assert result == []

    def test_word_boundary(self):
        # "nike" should match as a word, not inside "niked"
        result = scan_for_risk_terms("I niked the ball")
        assert result == []


class TestValidateTextContent:
    def test_valid_content(self):
        is_valid, terms = validate_text_content("Funny cat shirt for gift")
        assert is_valid is True
        assert terms == []

    def test_banned_content_invalid(self):
        is_valid, terms = validate_text_content("Murder themed shirt")
        assert is_valid is False
        assert "murder" in terms

    def test_risk_content_still_valid(self):
        is_valid, terms = validate_text_content("Disney style art")
        assert is_valid is True  # risk terms don't make it invalid
        assert "disney" in terms

    def test_mixed_banned_and_risk(self):
        is_valid, terms = validate_text_content("Nike murder shirt")
        assert is_valid is False
        assert "murder" in terms
        assert "nike" in terms
