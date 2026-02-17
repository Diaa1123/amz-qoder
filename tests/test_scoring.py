"""Tests for deterministic scoring functions."""

from __future__ import annotations

import pytest

from app.schemas import TrendEntry
from app.scoring.trend_scoring import (
    score_audience_size,
    score_commercial_intent,
    score_competition_level,
    score_designability,
    score_seasonality_risk,
    score_trademark_risk,
)


def _entry(
    query: str = "test",
    volume: int | None = None,
    growth_rate: float | None = None,
    category: str | None = None,
) -> TrendEntry:
    return TrendEntry(
        query=query, volume=volume, growth_rate=growth_rate, category=category,
    )


class TestScoreCommercialIntent:
    @pytest.mark.parametrize("query,expected_min", [
        ("funny cat shirt", 7),
        ("buy gift merch", 9),
        ("abstract philosophy", 1),
    ])
    def test_keyword_based(self, query: str, expected_min: int):
        score = score_commercial_intent(_entry(query=query))
        assert 1 <= score <= 10
        assert score >= expected_min

    def test_shopping_category_fallback(self):
        score = score_commercial_intent(
            _entry(query="random thing", category="Shopping"),
        )
        assert score >= 6


class TestScoreDesignability:
    @pytest.mark.parametrize("query,expected_min", [
        ("pixel art retro design", 7),
        ("galaxy cat illustration", 7),
        ("philosophy theory", 1),
    ])
    def test_visual_keywords(self, query: str, expected_min: int):
        score = score_designability(_entry(query=query))
        assert 1 <= score <= 10
        assert score >= expected_min


class TestScoreAudienceSize:
    @pytest.mark.parametrize("volume,expected", [
        (0, 1),
        (None, 1),
        (50000, 5),
        (100000, 10),
        (200000, 10),
    ])
    def test_volume_mapping(self, volume: int | None, expected: int):
        score = score_audience_size(_entry(volume=volume))
        assert 1 <= score <= 10
        assert abs(score - expected) <= 1  # allow +-1


class TestScoreCompetitionLevel:
    @pytest.mark.parametrize("growth_rate,max_expected", [
        (60.0, 4),   # high growth -> low competition
        (20.0, 6),
        (1.0, 8),    # stagnant -> high competition
    ])
    def test_growth_rate_inverse(self, growth_rate: float, max_expected: int):
        score = score_competition_level(_entry(growth_rate=growth_rate))
        assert 1 <= score <= 10
        assert score <= max_expected


class TestScoreSeasonalityRisk:
    def test_seasonal_keyword(self):
        score = score_seasonality_risk(_entry(query="christmas gift shirt"))
        assert score >= 7

    def test_no_seasonal_signal(self):
        score = score_seasonality_risk(_entry(query="funny cat"))
        assert score <= 4


class TestScoreTrademarkRisk:
    def test_trademark_keyword(self):
        score = score_trademark_risk(_entry(query="pokemon design"))
        assert score >= 7

    def test_no_trademark_signal(self):
        score = score_trademark_risk(_entry(query="retro gaming"))
        assert score <= 3


class TestScoreRanges:
    """All scoring functions must always return 1-10."""

    @pytest.mark.parametrize("fn", [
        score_commercial_intent,
        score_designability,
        score_audience_size,
        score_competition_level,
        score_seasonality_risk,
        score_trademark_risk,
    ])
    @pytest.mark.parametrize("query", [
        "hello world", "buy shirt gift", "pokemon christmas nike", "",
    ])
    def test_always_in_range(self, fn, query: str):
        score = fn(_entry(query=query, volume=50000, growth_rate=25.0))
        assert 1 <= score <= 10, f"{fn.__name__}({query!r}) returned {score}"
