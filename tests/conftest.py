"""Shared pytest fixtures for AMZ_Designy tests."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas import (
    AirtableRowIdea,
    AirtableRowNiche,
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheEntry,
    NicheReport,
    NicheScore,
    TrendEntry,
    TrendReport,
)


@pytest.fixture
def sample_trend_entry() -> TrendEntry:
    return TrendEntry(
        query="retro gaming shirt",
        volume=82000,
        growth_rate=45.3,
        category="Shopping",
        source="google_trends",
    )


@pytest.fixture
def sample_trend_report(sample_trend_entry: TrendEntry) -> TrendReport:
    return TrendReport(
        entries=[
            sample_trend_entry,
            TrendEntry(query="pixel art t-shirt", volume=51000, growth_rate=38.7),
        ],
        geo="US",
        timeframe="today 1-m",
        created_at=datetime(2026, 2, 17, 9, 15, 32),
    )


@pytest.fixture
def sample_niche_score() -> NicheScore:
    return NicheScore(
        commercial_intent=9,
        designability=9,
        audience_size=8,
        competition_level=6,
        seasonality_risk=3,
        trademark_risk=4,
    )


@pytest.fixture
def sample_niche_entry(sample_niche_score: NicheScore) -> NicheEntry:
    return NicheEntry(
        niche_name="Retro Gaming Nostalgia Apparel",
        trending_query="retro gaming shirt",
        score=sample_niche_score,
        audience="Gamers aged 25-45 who grew up with 80s/90s arcade games",
        analysis_summary="Strong commercial viability with clear design direction.",
    )


@pytest.fixture
def sample_niche_report(sample_niche_entry: NicheEntry) -> NicheReport:
    return NicheReport(
        entries=[sample_niche_entry],
        created_at=datetime(2026, 2, 17, 9, 18, 45),
    )


@pytest.fixture
def sample_idea_package() -> IdeaPackage:
    return IdeaPackage(
        niche_name="Retro Gaming Nostalgia Apparel",
        audience="Gamers aged 25-45 who grew up with 80s/90s arcade games",
        opportunity_score=7.90,
        final_approved_title="Retro Arcade Gamer - Pixel Perfect Nostalgia Tee",
        final_approved_bullet_points=[
            "Classic 8-bit pixel art design celebrating golden age of arcade gaming",
            "Perfect gift for gamers who remember feeding quarters into arcade machines",
            "Vintage-inspired graphics with authentic retro color palette",
            "Soft comfortable fit for casual gaming sessions or everyday wear",
            "Nostalgic tribute to the original console generation",
        ],
        final_approved_description=(
            "Take a trip down memory lane with this retro gaming t-shirt."
        ),
        final_approved_keywords_tags=[
            "retro gaming", "pixel art", "arcade gamer", "80s gaming",
            "vintage gaming",
        ],
        design_style="pixel art, 8-bit retro, vibrant arcade colors, high contrast",
        created_at=datetime(2026, 2, 17, 9, 22, 18),
    )


@pytest.fixture
def sample_design_prompt() -> DesignPrompt:
    return DesignPrompt(
        idea_niche_name="Retro Gaming Nostalgia Apparel",
        prompt_text=(
            "Create a vibrant pixel art design for a t-shirt celebrating "
            "retro arcade gaming."
        ),
        design_style="pixel art, 8-bit retro, vibrant arcade colors, high contrast",
        color_mood_notes="Primary: electric cyan, hot magenta, bright yellow.",
        created_at=datetime(2026, 2, 17, 9, 24, 55),
    )


@pytest.fixture
def sample_compliance_report() -> ComplianceReport:
    return ComplianceReport(
        idea_niche_name="Retro Gaming Nostalgia Apparel",
        compliance_status="approved",
        compliance_notes="All checks passed. No issues detected.",
        risk_terms_detected=[],
        created_at=datetime(2026, 2, 17, 9, 27, 33),
    )
